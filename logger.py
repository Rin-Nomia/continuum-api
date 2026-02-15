"""
logger.py
Continuum Logger (HF Space friendly) — ENTERPRISE AUDIT MODE (content-free)

Provides:
- DataLogger: log_analysis / log_feedback / get_stats
- GitHubBackup: optional restore hook (safe no-op by default)

Design goals:
- Never break the API if logging fails
- Avoid GitHub SHA race conditions by writing ONE FILE PER EVENT
- Works in Hugging Face Spaces using Secrets:
    GITHUB_TOKEN = GitHub Fine-grained PAT (Contents: Read & Write)
    GITHUB_REPO  = "owner/repo" (e.g., "Rin-Nomia/continuum-logs")

PRIVACY / GOVERNANCE GUARANTEE (重要):
- ✅ NO RAW TEXT is written to disk or GitHub.
- ✅ NO content-derived fragments are stored (matched keywords / oos matches / triggers).
- ✅ Only SHA256 fingerprints + lengths + decision evidence are logged.
- ✅ LOG_SALT is REQUIRED (startup will fail without it).

Compatibility:
- log_analysis(input_text=...) accepts str OR None.
- If input_text is provided, it is never stored; only fingerprint+len computed.
- Defense-in-depth: scrub risky keys inside output_result before writing.

PATCH (enterprise-hardening):
- ✅ Stronger scrub: key normalization (case/variant safe)
- ✅ Safe-by-default: drop any huge list/dict under suspicious keys
- ✅ Keep schema stable for app.py (no breaking changes)
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

import requests


# ----------------------------
# Time helpers
# ----------------------------
def _utc_dates():
    now = datetime.utcnow()
    return (
        now.strftime("%Y-%m"),   # year_month
        now.strftime("%Y%m%d"),  # date_str
        now.strftime("%H%M%S"),  # time_str
    )


def _utc_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


# ----------------------------
# Fingerprint helpers
# ----------------------------
def _get_salt() -> str:
    # Required for enterprise privacy hardening.
    return os.environ.get("LOG_SALT", "").strip()


def _sha256_hex(text: str, salt: str = "") -> str:
    raw = (salt + (text or "")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return int(default)


def _safe_str(v: Any, default: str = "") -> str:
    try:
        if v is None:
            return default
        return str(v)
    except Exception:
        return default


# ----------------------------
# Safety scrub (defense-in-depth)
# ----------------------------
# 1) Hard-drop obvious raw text fields (direct content)
_RISKY_TEXT_KEYS = {
    "text",
    "input_text",
    "original",
    "normalized",
    "repaired_text",
    "raw_ai_output",
    "llm_raw_response",
    "llm_raw_output",
    "prompt",
    "messages",
    "completion",
    "response_text",
}

# 2) Hard-drop derived-content fields (lists that leak content patterns)
_RISKY_DERIVED_KEYS = {
    "oos_matched",
    "matched",
    "matched_keywords",
    "matched_terms",
    "matched_phrases",
    "matched_patterns",
    "matched_rules",
    "lexicon_hits",
    "trigger_words",
    "trigger_terms",
    "hit_keywords",
    "hit_terms",
    "detected_keywords",
    "detected_terms",
    "detected_phrases",
    "keywords",
    "keyword_hits",
    "pattern_hits",
}

# 3) Size guards
_MAX_LIST_LEN = 80
_MAX_STR_LEN = 600
_MAX_DICT_KEYS = 120


def _k_norm(key: Any) -> str:
    """Normalize key for comparisons (case/variant safe)."""
    try:
        return str(key).strip().lower()
    except Exception:
        return ""


def _looks_like_sensitive_key(key: str) -> bool:
    k = (key or "").strip().lower()
    if not k:
        return False
    signals = [
        "text", "content", "message", "prompt", "completion", "response",
        "utterance", "transcript", "input", "output",
        "matched", "keyword", "trigger", "lexicon", "pattern", "phrase",
    ]
    return any(s in k for s in signals)


def _scrub_value_if_too_large(key: str, value: Any) -> Optional[Any]:
    """
    Returns:
      - None means "drop this field"
      - otherwise returns the (possibly trimmed) value
    """
    # Strings
    if isinstance(value, str):
        if len(value) > _MAX_STR_LEN and _looks_like_sensitive_key(key):
            return None
        return value

    # Lists
    if isinstance(value, list):
        if len(value) > _MAX_LIST_LEN and _looks_like_sensitive_key(key):
            return None
        if len(value) > _MAX_LIST_LEN:
            return value[:_MAX_LIST_LEN]
        return value

    # Dicts
    if isinstance(value, dict):
        if len(value.keys()) > _MAX_DICT_KEYS and _looks_like_sensitive_key(key):
            return None
        if len(value.keys()) > _MAX_DICT_KEYS:
            keys = sorted(list(value.keys()))[:_MAX_DICT_KEYS]
            return {k: value[k] for k in keys}
        return value

    return value


def _scrub_dict_content_free(obj: Any) -> Any:
    """
    Remove raw-text fields + derived-content fields recursively.
    Hard rules:
    - Never store known raw-text keys.
    - Never store known derived-content/match lists.
    - Drop suspicious oversized structures under sensitive keys.
    """
    if isinstance(obj, dict):
        out: Dict[str, Any] = {}
        for k, v in obj.items():
            kn = _k_norm(k)

            # hard-drop (case/variant safe)
            if kn in _RISKY_TEXT_KEYS:
                continue
            if kn in _RISKY_DERIVED_KEYS:
                continue

            # scrub recursively first
            scrubbed = _scrub_dict_content_free(v)

            # enforce size guards / sensitive heuristics
            guarded = _scrub_value_if_too_large(kn, scrubbed)
            if guarded is None:
                continue

            # keep original key as-is (schema stability)
            out[str(k)] = guarded
        return out

    if isinstance(obj, list):
        cleaned = [_scrub_dict_content_free(x) for x in obj]
        if len(cleaned) > _MAX_LIST_LEN:
            cleaned = cleaned[:_MAX_LIST_LEN]
        return cleaned

    return obj


# ----------------------------
# GitHub writer
# ----------------------------
class GitHubWriter:
    """
    Minimal GitHub Contents API writer.
    Writes one file per event to avoid SHA conflicts.
    """

    def __init__(self):
        self.github_token = os.environ.get("GITHUB_TOKEN")
        self.github_repo = os.environ.get("GITHUB_REPO")  # owner/repo
        self.github_ref = os.environ.get("GITHUB_REF", "").strip()  # optional branch/ref

        self.enabled = bool(self.github_token and self.github_repo)

        self.headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "continuum-api-logger",
        }
        if self.github_token:
            self.headers["Authorization"] = f"Bearer {self.github_token}"

    def _put_file(self, path: str, payload: Dict[str, Any]) -> bool:
        if not self.enabled:
            return False

        url = f"https://api.github.com/repos/{self.github_repo}/contents/{path}"
        if self.github_ref:
            # GitHub Contents API supports ?ref=branch
            url = url + f"?ref={self.github_ref}"

        content_bytes = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        b64 = base64.b64encode(content_bytes).decode("utf-8")

        data = {
            "message": f"Add log {payload.get('id', '')}".strip(),
            "content": b64,
        }

        try:
            r = requests.put(url, headers=self.headers, json=data, timeout=15)
            if r.status_code in (200, 201):
                return True
            # keep error output small (avoid leaking anything)
            txt = (r.text or "")[:120]
            print(f"[GitHubWriter] PUT failed {r.status_code}: {txt}")
            return False
        except Exception as e:
            print(f"[GitHubWriter] PUT exception: {e}")
            return False

    def write_event(self, category: str, event: Dict[str, Any], event_id: str) -> bool:
        year_month, date_str, _ = _utc_dates()
        path = f"logs/{year_month}/{date_str}/{category}/{event_id}.json"
        return self._put_file(path, event)


# ----------------------------
# DataLogger
# ----------------------------
class DataLogger:
    """
    API-facing logger used by app.py.

    ENTERPRISE AUDIT MODE:
    - log_analysis() never stores raw input/output text.
    - It stores only fingerprints + lengths + decision evidence passed in output_result.
    """

    def __init__(self, log_dir: str = "logs"):
        self.log_dir = log_dir
        self.writer = GitHubWriter()
        os.makedirs(self.log_dir, exist_ok=True)
        self.usage_dir = os.path.join(self.log_dir, "usage")
        os.makedirs(self.usage_dir, exist_ok=True)

        self._analysis_count = 0
        self._feedback_count = 0
        self._last_analysis_ts: Optional[str] = None

        if self.writer.enabled:
            print(f"[DataLogger] GitHub logging enabled -> {os.environ.get('GITHUB_REPO')}")
        else:
            print("[DataLogger] GitHub credentials not set; logging will be runtime-only (in-memory stats).")

        self._salt = _get_salt()
        if not self._salt:
            # Fail-fast: never allow runtime to operate in unsalted mode.
            raise RuntimeError(
                "CRITICAL_SECURITY_ERROR: LOG_SALT is required. "
                "Refusing to start without salted fingerprints."
            )
        print("[DataLogger] LOG_SALT enabled (fingerprints salted).")

        # Signed usage accounting (content-free)
        self._usage_signing_key = os.environ.get("USAGE_SIGNING_KEY", "").strip() or self._salt
        self._usage_lock = threading.Lock()
        self.usage_db_path = os.environ.get("USAGE_DB_PATH", os.path.join(self.log_dir, "usage.db"))
        self._init_usage_db()

    @staticmethod
    def _new_id(prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex[:12]}"

    def log_analysis(
        self,
        input_text: Optional[str],
        output_result: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        ts = _utc_iso()
        event_id = self._new_id("a")

        # If app.py passes None (recommended), we do NOT compute from raw text.
        if input_text is None:
            in_len = None
            in_fp = None
            try:
                if isinstance(output_result, dict):
                    in_fp = output_result.get("input_fp_sha256")
                    in_len = output_result.get("input_length")
            except Exception:
                in_fp, in_len = None, None
        else:
            in_len = len(input_text or "")
            in_fp = _sha256_hex(input_text or "", salt=self._salt)

        # output_result should already be content-free (recommended),
        # but we still enforce a safety scrub for risky keys (defense-in-depth).
        base_obj: Dict[str, Any] = output_result if isinstance(output_result, dict) else {}
        safe_result = _scrub_dict_content_free(dict(base_obj))

        payload: Dict[str, Any] = {
            "id": event_id,
            "timestamp": ts,
            "type": "analysis",
            "input": {
                "fp_sha256": _safe_str(in_fp, ""),
                "length": _safe_int(in_len, 0) if in_len is not None else None,
                "fingerprint_salted": bool(self._salt),
                "input_text_provided": input_text is not None,
            },
            "evidence": safe_result,
            "metadata": metadata or {},
            "runtime": {
                "source": "hf_space",
                "logger_mode": "enterprise_audit_content_free",
            },
        }

        self._analysis_count += 1
        self._last_analysis_ts = ts
        self._record_usage("analysis_count")
        self._append_usage_event(
            event_id=event_id,
            event_type="analysis",
            decision_state=self._event_decision_state(safe_result),
            mode=_safe_str(safe_result.get("mode"), ""),
            reason_code=self._event_reason_code(safe_result),
            llm_used=bool(safe_result.get("llm_used")),
            cache_hit=bool(safe_result.get("cache_hit")),
            latency_ms=self._event_latency_ms(safe_result),
        )

        if self.writer.enabled:
            ok = self.writer.write_event(category="analysis", event=payload, event_id=event_id)
            if not ok:
                payload["github_write"] = "failed"

        return {"timestamp": event_id, "created_at": ts}

    def log_feedback(self, log_id: str, accuracy: int, helpful: int, accepted: bool) -> Dict[str, Any]:
        ts = _utc_iso()
        event_id = self._new_id("f")

        payload = {
            "id": event_id,
            "timestamp": ts,
            "type": "feedback",
            "target_log_id": _safe_str(log_id, ""),
            "feedback": {
                "accuracy": _safe_int(accuracy, 0),
                "helpful": _safe_int(helpful, 0),
                "accepted": bool(accepted),
            },
            "runtime": {"source": "hf_space"},
        }

        self._feedback_count += 1
        self._record_usage("feedback_count")
        self._append_usage_event(
            event_id=event_id,
            event_type="feedback",
            decision_state="FEEDBACK",
            mode="",
            reason_code="",
            llm_used=False,
            cache_hit=False,
            latency_ms=None,
        )

        if self.writer.enabled:
            ok = self.writer.write_event(category="feedback", event=payload, event_id=event_id)
            if not ok:
                payload["github_write"] = "failed"

        return {"status": "ok", "feedback_id": event_id, "created_at": ts}

    def log_error_event(self, reason_code: str) -> Dict[str, Any]:
        ts = _utc_iso()
        event_id = self._new_id("e")
        self._analysis_count += 1
        self._last_analysis_ts = ts
        self._record_usage("analysis_count")
        self._append_usage_event(
            event_id=event_id,
            event_type="error",
            decision_state="ERROR",
            mode="error",
            reason_code=_safe_str(reason_code, "pipeline_error"),
            llm_used=False,
            cache_hit=False,
            latency_ms=None,
        )
        return {"status": "ok", "error_event_id": event_id, "created_at": ts}

    def _event_decision_state(self, safe_result: Dict[str, Any]) -> str:
        decision = _safe_str((safe_result or {}).get("decision_state"), "").upper()
        if decision in {"ALLOW", "GUIDE", "BLOCK", "ERROR"}:
            return decision
        mode = _safe_str((safe_result or {}).get("mode"), "").lower()
        if mode in {"block"}:
            return "BLOCK"
        if mode in {"suggest", "repair"}:
            return "GUIDE"
        if mode in {"no-op", "noop", "allow", "pass"}:
            return "ALLOW"
        if mode in {"error", "failed"}:
            return "ERROR"
        return "ERROR"

    def _event_reason_code(self, safe_result: Dict[str, Any]) -> str:
        metrics = (safe_result or {}).get("metrics") or {}
        return _safe_str(metrics.get("reason_code"), "")

    def _event_latency_ms(self, safe_result: Dict[str, Any]) -> Optional[int]:
        metrics = (safe_result or {}).get("metrics") or {}
        value = metrics.get("latency_ms")
        if value is None:
            timing = ((safe_result or {}).get("audit") or {}).get("timing_ms") or {}
            value = timing.get("total")
        if value is None:
            return None
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None

    def get_stats(self) -> Dict[str, Any]:
        usage_snapshot = self.get_usage_snapshot()
        return {
            "logger": {
                "enabled": self.writer.enabled,
                "repo": os.environ.get("GITHUB_REPO") if self.writer.enabled else None,
                "ref": os.environ.get("GITHUB_REF") if self.writer.enabled else None,
                "salted": bool(self._salt),
            },
            "counts": {
                "analyses_in_runtime": self._analysis_count,
                "feedback_in_runtime": self._feedback_count,
            },
            "usage": usage_snapshot,
            "last_analysis_utc": self._last_analysis_ts,
        }

    # ----------------------------
    # Signed Usage Accounting
    # ----------------------------
    def _current_month(self) -> str:
        return _utc_dates()[0]

    def _record_usage(self, key: str) -> None:
        _ = key
        to_finalize = None
        with self._usage_lock:
            now_month = self._current_month()
            conn = self._db_connect()
            try:
                active_month = self._meta_get(conn, "active_month", now_month)
                if active_month != now_month:
                    to_finalize = active_month
                self._meta_set(conn, "active_month", now_month)
                conn.commit()
            finally:
                conn.close()

        # Finalize previous month outside lock.
        if to_finalize:
            try:
                self.emit_signed_monthly_summary(month=to_finalize)
            except Exception as e:
                print(f"[DataLogger] monthly summary finalize failed: {e}")

    def _canonical_bytes(self, payload: Dict[str, Any]) -> bytes:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def _sign_payload(self, payload: Dict[str, Any]) -> str:
        data = self._canonical_bytes(payload)
        return hmac.new(self._usage_signing_key.encode("utf-8"), data, hashlib.sha256).hexdigest()

    def _db_connect(self) -> sqlite3.Connection:
        os.makedirs(os.path.dirname(self.usage_db_path) or ".", exist_ok=True)
        conn = sqlite3.connect(self.usage_db_path, timeout=5)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_usage_db(self) -> None:
        conn = self._db_connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS usage_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    event_type TEXT NOT NULL,
                    ts_utc TEXT NOT NULL,
                    month TEXT NOT NULL,
                    day TEXT NOT NULL,
                    decision_state TEXT NOT NULL,
                    mode TEXT NOT NULL DEFAULT '',
                    reason_code TEXT NOT NULL DEFAULT '',
                    llm_used INTEGER NOT NULL DEFAULT 0,
                    cache_hit INTEGER NOT NULL DEFAULT 0,
                    latency_ms INTEGER,
                    heartbeat_counter INTEGER NOT NULL,
                    heartbeat_sig TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_events_month ON usage_events(month)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_events_day ON usage_events(day)")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_usage_events_day_decision ON usage_events(day, decision_state)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS usage_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            if self._meta_get(conn, "active_month", None) is None:
                self._meta_set(conn, "active_month", self._current_month())
            conn.commit()
        finally:
            conn.close()

    def _meta_get(self, conn: sqlite3.Connection, key: str, default: Optional[str]) -> Optional[str]:
        row = conn.execute("SELECT value FROM usage_meta WHERE key = ?", (key,)).fetchone()
        if not row:
            return default
        return _safe_str(row["value"], default if default is not None else "")

    def _meta_get_int(self, conn: sqlite3.Connection, key: str, default: int = 0) -> int:
        raw = self._meta_get(conn, key, str(default))
        try:
            return int(raw if raw is not None else default)
        except (TypeError, ValueError):
            return int(default)

    def _meta_set(self, conn: sqlite3.Connection, key: str, value: Any) -> None:
        conn.execute(
            """
            INSERT INTO usage_meta(key, value) VALUES(?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, str(value)),
        )

    def _heartbeat_signature(self, total_events: int, counter: int, event_id: str, ts_utc: str) -> str:
        payload = f"{total_events}|{counter}|{event_id}|{ts_utc}"
        return hmac.new(
            self._usage_signing_key.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _append_usage_event(
        self,
        event_id: str,
        event_type: str,
        decision_state: str,
        mode: str,
        reason_code: str,
        llm_used: bool,
        cache_hit: bool,
        latency_ms: Optional[int],
    ) -> None:
        with self._usage_lock:
            conn = self._db_connect()
            try:
                ts = _utc_iso()
                month_key, day_key, _ = _utc_dates()
                total_events = self._meta_get_int(conn, "total_events", 0) + 1
                counter = self._meta_get_int(conn, "heartbeat_counter", 0) + 1
                hb_sig = self._heartbeat_signature(total_events, counter, event_id, ts)

                conn.execute(
                    """
                    INSERT INTO usage_events(
                        event_id, event_type, ts_utc, month, day,
                        decision_state, mode, reason_code, llm_used,
                        cache_hit, latency_ms, heartbeat_counter, heartbeat_sig
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event_id,
                        _safe_str(event_type, "analysis"),
                        ts,
                        month_key,
                        day_key,
                        _safe_str(decision_state, "ERROR").upper(),
                        _safe_str(mode, ""),
                        _safe_str(reason_code, ""),
                        1 if llm_used else 0,
                        1 if cache_hit else 0,
                        int(latency_ms) if latency_ms is not None else None,
                        counter,
                        hb_sig,
                    ),
                )

                self._meta_set(conn, "total_events", total_events)
                self._meta_set(conn, "heartbeat_counter", counter)
                self._meta_set(conn, "last_event_id", event_id)
                self._meta_set(conn, "last_event_ts", ts)
                self._meta_set(conn, "last_heartbeat_sig", hb_sig)
                conn.commit()
            except Exception as exc:
                conn.rollback()
                print(f"[DataLogger] usage event write failed: {exc}")
            finally:
                conn.close()

    def _month_counts(self, month_key: str) -> Dict[str, int]:
        conn = self._db_connect()
        try:
            row = conn.execute(
                """
                SELECT
                    SUM(CASE WHEN event_type IN ('analysis', 'error') THEN 1 ELSE 0 END) AS analysis_count,
                    SUM(CASE WHEN event_type = 'feedback' THEN 1 ELSE 0 END) AS feedback_count,
                    COUNT(*) AS total_events
                FROM usage_events
                WHERE month = ?
                """,
                (month_key,),
            ).fetchone()
            return {
                "analysis_count": int(row["analysis_count"] or 0),
                "feedback_count": int(row["feedback_count"] or 0),
                "total_events": int(row["total_events"] or 0),
            }
        finally:
            conn.close()

    def _month_decision_counts(self, month_key: str) -> Dict[str, int]:
        conn = self._db_connect()
        try:
            rows = conn.execute(
                """
                SELECT decision_state, COUNT(*) AS c
                FROM usage_events
                WHERE month = ?
                  AND event_type IN ('analysis', 'error')
                GROUP BY decision_state
                """,
                (month_key,),
            ).fetchall()
            out: Dict[str, int] = {}
            for row in rows:
                out[_safe_str(row["decision_state"], "UNKNOWN")] = int(row["c"] or 0)
            return out
        finally:
            conn.close()

    def _heartbeat_status(self) -> Dict[str, Any]:
        conn = self._db_connect()
        try:
            total_events = self._meta_get_int(conn, "total_events", 0)
            counter = self._meta_get_int(conn, "heartbeat_counter", 0)
            event_id = self._meta_get(conn, "last_event_id", "") or ""
            ts_utc = self._meta_get(conn, "last_event_ts", "") or ""
            sig = self._meta_get(conn, "last_heartbeat_sig", "") or ""
        finally:
            conn.close()

        if not event_id:
            return {
                "ok": True,
                "reason": "no_events",
                "total_events": total_events,
                "heartbeat_counter": counter,
            }

        expected = self._heartbeat_signature(total_events, counter, event_id, ts_utc)
        ok = bool(sig) and hmac.compare_digest(expected, sig)
        return {
            "ok": ok,
            "reason": "ok" if ok else "signature_mismatch",
            "total_events": total_events,
            "heartbeat_counter": counter,
            "last_event_id": event_id,
            "last_event_ts": ts_utc,
        }

    def emit_signed_monthly_summary(self, month: Optional[str] = None) -> Dict[str, Any]:
        month_key = (month or self._current_month()).strip()
        counts = self._month_counts(month_key)
        decisions = self._month_decision_counts(month_key)
        heartbeat = self._heartbeat_status()

        payload = {
            "schema_version": "1.0",
            "month": month_key,
            "generated_at_utc": _utc_iso(),
            "counts": counts,
            "decision_counts": decisions,
            "heartbeat": heartbeat,
            "content_free": True,
            "signature_algorithm": "HMAC-SHA256",
        }
        signature = self._sign_payload(payload)

        summary_path = os.path.join(self.usage_dir, f"{month_key}.summary.json")
        sig_path = os.path.join(self.usage_dir, f"{month_key}.summary.sig")

        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        with open(sig_path, "w", encoding="utf-8") as f:
            f.write(signature + "\n")

        return {
            "month": month_key,
            "summary_path": summary_path,
            "sig_path": sig_path,
            "signature": signature,
            "counts": payload["counts"],
        }

    def get_usage_snapshot(self) -> Dict[str, Any]:
        month_key = self._current_month()
        counts = self._month_counts(month_key)
        heartbeat = self._heartbeat_status()
        return {
            "month": month_key,
            "analysis_in_month": int(counts.get("analysis_count", 0)),
            "feedback_in_month": int(counts.get("feedback_count", 0)),
            "summary_dir": self.usage_dir,
            "usage_db_path": self.usage_db_path,
            "signature_algorithm": "HMAC-SHA256",
            "signing_key_configured": bool(self._usage_signing_key),
            "heartbeat": heartbeat,
        }


# ----------------------------
# GitHubBackup (safe no-op)
# ----------------------------
class GitHubBackup:
    """
    Compatibility class: app.py calls GitHubBackup(...).restore()
    For this stable version, restore is intentionally a safe no-op.
    """

    def __init__(self, log_dir: str = "logs"):
        self.log_dir = log_dir

    def restore(self) -> None:
        print("[GitHubBackup] restore() skipped (no-op)")
        return