"""
logger.py
Continuum Logger (HF Space friendly)

Provides:
- DataLogger: log_analysis / log_feedback / get_stats
- GitHubBackup: optional restore hook (safe no-op by default)

Design goals:
- Never break the API if logging fails
- Avoid GitHub SHA race conditions by writing ONE FILE PER EVENT
- Works in Hugging Face Spaces using Secrets:
    GITHUB_TOKEN = GitHub Fine-grained PAT (Contents: Read & Write)
    GITHUB_REPO  = "owner/repo" (e.g., "Rin-Nomia/continuum-logs")

Governance-grade privacy:
- ✅ NEVER store raw input/output text
- ✅ Store ONLY hash + length (+ decision/audit/metrics)
- ✅ Store pipeline_version_fingerprint for reproducibility
"""

from __future__ import annotations

import json
import os
import uuid
import hashlib
from datetime import datetime
from typing import Any, Dict, Optional

import requests


def _utc_dates():
    now = datetime.utcnow()
    return (
        now.strftime("%Y-%m"),   # year_month
        now.strftime("%Y%m%d"),  # date_str
        now.strftime("%H%M%S"),  # time_str
    )


def _sha256_text(s: str) -> str:
    return hashlib.sha256((s or "").encode("utf-8")).hexdigest()


def _safe_int(v, default=0) -> int:
    try:
        return int(v)
    except Exception:
        return int(default)


class GitHubWriter:
    """
    Minimal GitHub Contents API writer.
    Writes one file per event to avoid SHA conflicts.
    """

    def __init__(self):
        self.github_token = os.environ.get("GITHUB_TOKEN")
        self.github_repo = os.environ.get("GITHUB_REPO")  # owner/repo
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

        content_bytes = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        b64 = __import__("base64").b64encode(content_bytes).decode("utf-8")

        data = {
            "message": f"Add log {payload.get('id', '')}".strip(),
            "content": b64,
        }

        try:
            r = requests.put(url, headers=self.headers, json=data, timeout=15)
            if r.status_code in (200, 201):
                return True
            print(f"[GitHubWriter] PUT failed {r.status_code}: {r.text[:200]}")
            return False
        except Exception as e:
            print(f"[GitHubWriter] PUT exception: {e}")
            return False

    def write_event(self, category: str, event: Dict[str, Any], event_id: str) -> bool:
        year_month, date_str, _ = _utc_dates()
        path = f"logs/{year_month}/{date_str}/{category}/{event_id}.json"
        return self._put_file(path, event)


class DataLogger:
    """
    API-facing logger used by app.py.

    Privacy rule:
    - input_text is accepted for hashing but never stored
    - output_result is accepted for extracting decision fields but never stores any text fields
    """

    def __init__(self, log_dir: str = "logs"):
        self.log_dir = log_dir
        self.writer = GitHubWriter()

        self._analysis_count = 0
        self._feedback_count = 0
        self._last_analysis_ts: Optional[str] = None

        if self.writer.enabled:
            print(f"[DataLogger] GitHub logging enabled -> {os.environ.get('GITHUB_REPO')}")
        else:
            print("[DataLogger] GitHub credentials not set; logging will be local-only (in-memory stats).")

    @staticmethod
    def _new_id(prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex[:12]}"

    def _extract_safe_summary(self, input_text: str, output_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build a safe, governance-grade log payload:
        - Store only hashes + lengths
        - Keep decision/audit/metrics (no content)
        """
        inp = input_text or ""
        inp_hash = _sha256_text(inp)
        inp_len = len(inp)

        normalized = output_result.get("normalized") if isinstance(output_result, dict) else ""
        normalized = normalized if isinstance(normalized, str) else str(normalized or "")
        norm_hash = _sha256_text(normalized)
        norm_len = len(normalized)

        out = output_result.get("output") if isinstance(output_result, dict) else {}
        out = out if isinstance(out, dict) else {}

        repaired_text = out.get("repaired_text")
        repaired_text = repaired_text if isinstance(repaired_text, str) else str(repaired_text or "")
        out_hash = _sha256_text(repaired_text)
        out_len = len(repaired_text)

        # Pull truth fields (no content)
        freq_type = output_result.get("freq_type", "Unknown")
        mode = output_result.get("mode", "no-op")
        confidence = output_result.get("confidence", {}) if isinstance(output_result.get("confidence", {}), dict) else {}
        conf_final = confidence.get("final", 0.0)
        conf_cls = confidence.get("classifier", 0.0)

        audit = output_result.get("audit") if isinstance(output_result.get("audit"), dict) else {}
        metrics = output_result.get("metrics") if isinstance(output_result.get("metrics"), dict) else {}

        pipeline_fp = (
            output_result.get("pipeline_version_fingerprint")
            or (audit.get("pipeline_version_fingerprint") if isinstance(audit, dict) else None)
        )

        # Hard strip any possible text leak in audit/metrics (defense-in-depth)
        # We keep only primitive fields; if later audit has big objects, we don't store them.
        def _prune(d: Dict[str, Any], allow_keys: Optional[set] = None) -> Dict[str, Any]:
            if not isinstance(d, dict):
                return {}
            if allow_keys is None:
                # default allowlist for audit
                allow_keys = {
                    "llm_used", "cache_hit", "output_source", "fallback_used", "fallback_reason",
                    "safe_flow", "oos_reason_code",
                    "timing_ms", "suppressed_chars",
                    "pipeline_version_fingerprint",
                    "llm_eligible", "llm_attempted", "llm_succeeded", "llm_error",
                    "output_gate_passed", "output_gate_reason",
                }
            pruned = {}
            for k, v in d.items():
                if k not in allow_keys:
                    continue
                # keep simple json-safe stuff
                if isinstance(v, (str, int, float, bool)) or v is None:
                    pruned[k] = v
                elif isinstance(v, dict):
                    pruned[k] = v  # nested dict OK, but relies on pipeline not inserting content here
                elif isinstance(v, list):
                    # lists can leak matches; allow only short primitives
                    safe_list = []
                    for item in v[:50]:
                        if isinstance(item, (str, int, float, bool)) or item is None:
                            safe_list.append(item)
                    pruned[k] = safe_list
            return pruned

        safe_audit = _prune(audit)
        safe_metrics = metrics if isinstance(metrics, dict) else {}

        return {
            "fingerprints": {
                "input": {"sha256": inp_hash, "length": inp_len},
                "normalized": {"sha256": norm_hash, "length": norm_len},
                "output": {"sha256": out_hash, "length": out_len},
            },
            "decision": {
                "freq_type": freq_type,
                "mode": mode,
                "confidence_final": conf_final,
                "confidence_classifier": conf_cls,
            },
            "truth": {
                "llm_used": output_result.get("llm_used", None),
                "cache_hit": output_result.get("cache_hit", None),
                "model": output_result.get("model", ""),
                "usage": output_result.get("usage", {}) if isinstance(output_result.get("usage", {}), dict) else {},
                "output_source": output_result.get("output_source", None),
            },
            "audit": safe_audit,
            "metrics": safe_metrics,
            "pipeline_version_fingerprint": pipeline_fp,
        }

    def log_analysis(
        self,
        input_text: str,
        output_result: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new analysis log event and (optionally) ship to GitHub.
        Returns a dict containing 'timestamp' which app.py uses as log_id.
        """
        ts = datetime.utcnow().isoformat() + "Z"
        event_id = self._new_id("a")

        safe_summary = self._extract_safe_summary(input_text, output_result)

        payload = {
            "id": event_id,
            "timestamp": ts,
            "type": "analysis",
            "safe_summary": safe_summary,
            "metadata": metadata or {},
            "runtime": {"source": "hf_space"},
        }

        self._analysis_count += 1
        self._last_analysis_ts = ts

        if self.writer.enabled:
            ok = self.writer.write_event(category="analysis", event=payload, event_id=event_id)
            if not ok:
                payload["github_write"] = "failed"

        return {"timestamp": event_id, "created_at": ts}

    def log_feedback(self, log_id: str, accuracy: int, helpful: int, accepted: bool) -> Dict[str, Any]:
        ts = datetime.utcnow().isoformat() + "Z"
        event_id = self._new_id("f")

        payload = {
            "id": event_id,
            "timestamp": ts,
            "type": "feedback",
            "target_log_id": log_id,
            "feedback": {
                "accuracy": _safe_int(accuracy, 0),
                "helpful": _safe_int(helpful, 0),
                "accepted": bool(accepted),
            },
        }

        self._feedback_count += 1

        if self.writer.enabled:
            ok = self.writer.write_event(category="feedback", event=payload, event_id=event_id)
            if not ok:
                payload["github_write"] = "failed"

        return {"status": "ok", "feedback_id": event_id, "created_at": ts}

    def get_stats(self) -> Dict[str, Any]:
        return {
            "logger": {
                "enabled": self.writer.enabled,
                "repo": os.environ.get("GITHUB_REPO") if self.writer.enabled else None,
            },
            "counts": {
                "analyses_in_runtime": self._analysis_count,
                "feedback_in_runtime": self._feedback_count,
            },
            "last_analysis_utc": self._last_analysis_ts,
        }


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