#!/usr/bin/env python3
"""
Continuum Command Center (C3)

Independent operations dashboard for commercial v1.1.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import sqlite3
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd
import streamlit as st


APP_DIR = Path(__file__).resolve().parent
WORKSPACE_DIR = APP_DIR.parent
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

try:
    from core.license_manager import LicenseManager
except Exception:
    LicenseManager = None  # type: ignore[assignment]


PRICING_TABLE = {
    "LITE": {"base_monthly_usd": 99, "included_quota": 5_000, "overage_per_1k_usd": 6.0},
    "PRO": {"base_monthly_usd": 499, "included_quota": 50_000, "overage_per_1k_usd": 3.0},
    "ENTERPRISE": {"base_monthly_usd": 1_999, "included_quota": 500_000, "overage_per_1k_usd": 1.8},
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today_utc() -> datetime:
    return datetime.now(timezone.utc)


def _default_usage_db_path() -> Path:
    return Path(os.environ.get("USAGE_DB_PATH", str(APP_DIR / "logs" / "usage.db")))


def _default_license_file() -> Path:
    return Path(os.environ.get("LICENSE_FILE", str(APP_DIR / "license" / "license.enc")))


def _signing_key() -> str:
    return (os.environ.get("USAGE_SIGNING_KEY", "").strip() or os.environ.get("LOG_SALT", "").strip())


def _admin_password() -> str:
    return os.environ.get("C3_ADMIN_PASSWORD", "").strip()


def _admin_password_hash() -> str:
    return os.environ.get("C3_ADMIN_PASSWORD_HASH", "").strip()


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)).strip())
    except (TypeError, ValueError):
        return int(default)


def _password_policy_ok(secret: str) -> Tuple[bool, str]:
    if len(secret) < 12:
        return False, "password_too_short"
    if not re.search(r"[A-Z]", secret):
        return False, "missing_uppercase"
    if not re.search(r"[a-z]", secret):
        return False, "missing_lowercase"
    if not re.search(r"[0-9]", secret):
        return False, "missing_digit"
    if not re.search(r"[^A-Za-z0-9]", secret):
        return False, "missing_symbol"
    return True, "ok"


def _kdf_key(secret: str) -> bytes:
    return hashlib.sha256((secret or "").encode("utf-8")).digest()


def _keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < length:
        block = hashlib.sha256(key + nonce + counter.to_bytes(8, "big")).digest()
        out.extend(block)
        counter += 1
    return bytes(out[:length])


def _xor_stream(raw: bytes, secret: str, nonce: bytes) -> bytes:
    key = _kdf_key(secret)
    ks = _keystream(key, nonce, len(raw))
    return bytes(a ^ b for a, b in zip(raw, ks))


def _encrypt_payload(payload: Dict[str, Any], secret: str) -> Dict[str, str]:
    if LicenseManager is not None:
        return LicenseManager.encrypt_payload(payload, secret)
    nonce = os.urandom(16)
    plain = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ciphertext = _xor_stream(plain, secret, nonce)
    digest = hmac.new(_kdf_key(secret), nonce + ciphertext, hashlib.sha256).hexdigest()
    return {
        "version": "1.0",
        "nonce_b64": base64.b64encode(nonce).decode("utf-8"),
        "ciphertext_b64": base64.b64encode(ciphertext).decode("utf-8"),
        "signature_hex": digest,
    }


def _decrypt_payload(envelope: Dict[str, Any], secret: str) -> Dict[str, Any]:
    if LicenseManager is not None:
        return LicenseManager.decrypt_payload(envelope, secret)
    nonce = base64.b64decode(envelope.get("nonce_b64", ""))
    ciphertext = base64.b64decode(envelope.get("ciphertext_b64", ""))
    sig_hex = str(envelope.get("signature_hex", "")).strip().lower()
    expected = hmac.new(_kdf_key(secret), nonce + ciphertext, hashlib.sha256).hexdigest().lower()
    if not hmac.compare_digest(expected, sig_hex):
        raise RuntimeError("signature_mismatch")
    plain = _xor_stream(ciphertext, secret, nonce)
    return json.loads(plain.decode("utf-8"))


def _pbkdf2_digest(secret: str, salt_raw: bytes, iterations: int) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256",
        secret.encode("utf-8"),
        salt_raw,
        iterations,
    ).hex()


def _verify_admin_secret(candidate: str) -> bool:
    pwd_hash = _admin_password_hash()
    if pwd_hash:
        # Format: pbkdf2_sha256$260000$<salt_b64>$<digest_hex>
        parts = pwd_hash.split("$")
        if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
            return False
        try:
            iterations = int(parts[1])
            salt_raw = base64.b64decode(parts[2].encode("utf-8"))
        except Exception:
            return False
        expected = parts[3].strip().lower()
        actual = _pbkdf2_digest(candidate, salt_raw, iterations)
        return hmac.compare_digest(actual, expected)

    plain = _admin_password()
    return bool(plain) and hmac.compare_digest(candidate, plain)


def _connect_usage_db_readonly(path: Path) -> sqlite3.Connection:
    uri = f"file:{path.resolve()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _load_license_payload(license_file: Path, license_key: str) -> Tuple[Dict[str, Any], str]:
    if not license_file.exists():
        return {}, "license_file_missing"
    if not license_key:
        return {}, "license_key_missing"

    try:
        envelope = json.loads(license_file.read_text(encoding="utf-8"))
    except Exception as exc:
        return {}, f"license_file_invalid_json:{exc}"

    try:
        payload = _decrypt_payload(envelope, license_key)
        if not isinstance(payload, dict):
            return {}, "license_payload_not_dict"
        return payload, "ok"
    except Exception as exc:
        return {}, f"license_decrypt_failed:{exc}"


def _license_days_left(expiry_date: str) -> int:
    try:
        expiry = datetime.fromisoformat(expiry_date).date()
    except Exception:
        return -1
    return (expiry - _today_utc().date()).days


def _license_tier(payload: Dict[str, Any]) -> str:
    tier = str(payload.get("tier", payload.get("plan", "PRO"))).strip().upper()
    return tier if tier in PRICING_TABLE else "PRO"


def _fetch_monthly_counts(conn: sqlite3.Connection, month_key: str) -> Dict[str, int]:
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
        "analysis_count": _safe_int(row["analysis_count"] if row else 0),
        "feedback_count": _safe_int(row["feedback_count"] if row else 0),
        "total_events": _safe_int(row["total_events"] if row else 0),
    }


def _fetch_decision_distribution_30d(conn: sqlite3.Connection) -> pd.DataFrame:
    since = (_today_utc() - timedelta(days=29)).date().isoformat()
    rows = conn.execute(
        """
        SELECT
            day,
            CASE
                WHEN decision_state = 'ALLOW' THEN 'ALLOW'
                WHEN decision_state IN ('GUIDE', 'BLOCK') THEN 'GUIDE'
                ELSE 'ERROR'
            END AS decision_bucket,
            COUNT(*) AS c
        FROM usage_events
        WHERE event_type IN ('analysis', 'error')
          AND day >= ?
        GROUP BY day, decision_bucket
        ORDER BY day ASC
        """,
        (since,),
    ).fetchall()
    if not rows:
        return pd.DataFrame(columns=["day", "decision_bucket", "count"])
    out = pd.DataFrame([{"day": r["day"], "decision_bucket": r["decision_bucket"], "count": int(r["c"])} for r in rows])
    return out


def _fetch_decision_health(conn: sqlite3.Connection) -> Dict[str, Any]:
    since_24h = (_today_utc() - timedelta(hours=24)).isoformat()
    row = conn.execute(
        """
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN decision_state = 'ERROR' OR event_type = 'error' THEN 1 ELSE 0 END) AS error_count
        FROM usage_events
        WHERE event_type IN ('analysis', 'error')
          AND ts_utc >= ?
        """,
        (since_24h,),
    ).fetchone()
    total = _safe_int(row["total"] if row else 0)
    error_count = _safe_int(row["error_count"] if row else 0)
    error_rate = (error_count / total) if total > 0 else 0.0
    if total == 0:
        status = "NO_TRAFFIC"
    elif error_rate <= 0.02:
        status = "HEALTHY"
    elif error_rate <= 0.08:
        status = "WATCH"
    else:
        status = "RISK"
    return {"status": status, "total_24h": total, "error_rate_24h": round(error_rate, 4)}


def _fetch_usage_meta(conn: sqlite3.Connection) -> Dict[str, str]:
    try:
        rows = conn.execute("SELECT key, value FROM usage_meta").fetchall()
    except sqlite3.OperationalError:
        return {}
    return {str(row["key"]): str(row["value"]) for row in rows}


def _verify_heartbeat(meta: Dict[str, str], key: str) -> Dict[str, Any]:
    total_events = _safe_int(meta.get("total_events"), 0)
    counter = _safe_int(meta.get("heartbeat_counter"), 0)
    last_event_id = str(meta.get("last_event_id", "")).strip()
    last_event_ts = str(meta.get("last_event_ts", "")).strip()
    last_sig = str(meta.get("last_heartbeat_sig", "")).strip().lower()

    if not last_event_id:
        return {
            "ok": True,
            "reason": "no_events",
            "total_events": total_events,
            "heartbeat_counter": counter,
        }
    if not key:
        return {
            "ok": False,
            "reason": "missing_signing_key",
            "total_events": total_events,
            "heartbeat_counter": counter,
        }

    payload = f"{total_events}|{counter}|{last_event_id}|{last_event_ts}".encode("utf-8")
    expected = hmac.new(key.encode("utf-8"), payload, hashlib.sha256).hexdigest().lower()
    ok = bool(last_sig) and hmac.compare_digest(expected, last_sig)
    return {
        "ok": ok,
        "reason": "ok" if ok else "signature_mismatch",
        "total_events": total_events,
        "heartbeat_counter": counter,
        "last_event_id": last_event_id,
        "last_event_ts": last_event_ts,
    }


def _build_cost_estimate(tier: str, usage_count: int, quota_limit: int) -> Dict[str, Any]:
    cfg = PRICING_TABLE.get(tier.upper(), PRICING_TABLE["PRO"])
    included_quota = int(cfg["included_quota"])
    effective_quota = max(quota_limit, included_quota)
    overage = max(0, usage_count - effective_quota)
    overage_units = overage / 1000.0
    overage_fee = round(overage_units * float(cfg["overage_per_1k_usd"]), 2)
    projected_total = round(float(cfg["base_monthly_usd"]) + overage_fee, 2)
    quota_progress = 0.0 if effective_quota <= 0 else min(1.0, usage_count / effective_quota)
    return {
        "base_monthly_usd": float(cfg["base_monthly_usd"]),
        "included_quota": effective_quota,
        "overage_count": overage,
        "overage_fee_usd": overage_fee,
        "projected_total_usd": projected_total,
        "quota_progress": quota_progress,
    }


def _generate_evidence_summary_sig(
    db_path: Path,
    output_dir: Path,
    signing_key: str,
    license_payload: Dict[str, Any],
) -> Tuple[Path, Dict[str, Any]]:
    if not signing_key:
        raise RuntimeError("missing_signing_key")
    output_dir.mkdir(parents=True, exist_ok=True)
    month_key = _today_utc().strftime("%Y-%m")

    with _connect_usage_db_readonly(db_path) as conn:
        counts = _fetch_monthly_counts(conn, month_key)
        trend_df = _fetch_decision_distribution_30d(conn)
        meta = _fetch_usage_meta(conn)
        heartbeat = _verify_heartbeat(meta, signing_key)

    trend_rollup = (
        trend_df.groupby("decision_bucket")["count"].sum().to_dict()
        if not trend_df.empty
        else {}
    )
    payload = {
        "schema_version": "1.0",
        "generated_at_utc": _utc_now(),
        "month": month_key,
        "license": {
            "license_id": str(license_payload.get("license_id", "")),
            "customer_name": str(license_payload.get("customer_name", "unknown")),
            "uid": str(license_payload.get("uid", "")),
            "tier": _license_tier(license_payload),
        },
        "counts": counts,
        "decision_bucket_30d": trend_rollup,
        "heartbeat": heartbeat,
        "content_free": True,
        "signature_algorithm": "HMAC-SHA256",
    }

    envelope = _encrypt_payload(payload, signing_key)

    target = output_dir / "EVIDENCE_SUMMARY.sig"
    target.write_text(json.dumps(envelope, ensure_ascii=False, indent=2), encoding="utf-8")
    return target, payload


def _export_scrub_log(
    db_path: Path,
    output_dir: Path,
    api_version: str,
) -> Tuple[Path, Dict[str, Any]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = _today_utc().strftime("%Y%m%dT%H%M%SZ")

    with _connect_usage_db_readonly(db_path) as conn:
        rows = conn.execute(
            """
            SELECT event_id, ts_utc, decision_state, mode, reason_code, llm_used, cache_hit, latency_ms
            FROM usage_events
            WHERE event_type IN ('analysis', 'error')
            ORDER BY ts_utc DESC
            LIMIT 5000
            """
        ).fetchall()

    records: List[Dict[str, Any]] = []
    for row in rows:
        event_id = str(row["event_id"])
        records.append(
            {
                "schema_version": "1.0",
                "input_fp_sha256": hashlib.sha256(f"in:{event_id}".encode("utf-8")).hexdigest(),
                "input_length": 0,
                "output_fp_sha256": hashlib.sha256(f"out:{event_id}".encode("utf-8")).hexdigest(),
                "output_length": 0,
                "freq_type": "Unknown",
                "mode": str(row["mode"] or ""),
                "scenario": "compliance_export",
                "confidence": {"final": 0.0, "classifier": 0.0},
                "metrics": {
                    "decision_state": str(row["decision_state"] or "ERROR"),
                    "reason_code": str(row["reason_code"] or ""),
                    "latency_ms": _safe_int(row["latency_ms"], 0),
                },
                "audit": {
                    "source": "usage_db_export",
                    "event_id": event_id,
                    "ts_utc": str(row["ts_utc"] or ""),
                },
                "llm_used": bool(_safe_int(row["llm_used"], 0)),
                "cache_hit": bool(_safe_int(row["cache_hit"], 0)),
                "model": "",
                "usage": {},
                "output_source": "usage_db_export",
                "api_version": api_version,
                "pipeline_version_fingerprint": "",
            }
        )

    payload = {
        "schema_version": "1.0",
        "generated_at_utc": _utc_now(),
        "record_count": len(records),
        "content_free": True,
        "records": records,
    }
    target = output_dir / f"scrub_log_export_{timestamp}.json"
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target, payload


def _update_license_file(uploaded_bytes: bytes, license_file: Path, license_key: str) -> Dict[str, Any]:
    if not uploaded_bytes:
        raise RuntimeError("empty_uploaded_file")
    if not license_key:
        raise RuntimeError("missing_license_key")

    raw = uploaded_bytes.decode("utf-8")
    envelope = json.loads(raw)
    payload = _decrypt_payload(envelope, license_key)
    if not isinstance(payload, dict):
        raise RuntimeError("license_payload_not_dict")

    license_file.parent.mkdir(parents=True, exist_ok=True)
    if license_file.exists():
        backup = license_file.with_suffix(license_file.suffix + f".bak.{_today_utc().strftime('%Y%m%d%H%M%S')}")
        backup.write_text(license_file.read_text(encoding="utf-8"), encoding="utf-8")
    license_file.write_bytes(uploaded_bytes)
    return payload


def _render_login() -> None:
    st.title("Continuum Command Center (C3)")
    st.caption("Commercial operations dashboard (localhost only)")
    admin_pwd = _admin_password()
    admin_hash = _admin_password_hash()
    if not admin_pwd and not admin_hash:
        st.error("C3_ADMIN_PASSWORD or C3_ADMIN_PASSWORD_HASH is required.")
        st.stop()

    if admin_pwd and not admin_hash:
        strong, reason = _password_policy_ok(admin_pwd)
        if not strong:
            st.error(
                f"Weak C3_ADMIN_PASSWORD ({reason}). "
                "Use >=12 chars with upper/lower/digit/symbol or set C3_ADMIN_PASSWORD_HASH."
            )
            st.stop()

    max_attempts = max(1, _int_env("C3_LOGIN_MAX_ATTEMPTS", 5))
    lockout_seconds = max(30, _int_env("C3_LOCKOUT_SECONDS", 900))
    session_ttl_seconds = max(300, _int_env("C3_SESSION_TTL_SECONDS", 1800))
    now = time.time()

    authed_at = float(st.session_state.get("c3_authed_at", 0.0))
    if st.session_state.get("c3_authed") and authed_at > 0 and now - authed_at > session_ttl_seconds:
        st.session_state["c3_authed"] = False
        st.session_state["c3_authed_at"] = 0.0
        st.warning("Session expired. Please re-authenticate.")

    if st.session_state.get("c3_authed"):
        return

    locked_until = float(st.session_state.get("c3_locked_until", 0.0))
    if now < locked_until:
        remain = int(locked_until - now)
        st.error(f"Too many failed attempts. Retry in {remain}s.")
        st.stop()

    with st.form("c3_login_form"):
        pwd = st.text_input("Admin Password", type="password")
        submit = st.form_submit_button("Login")
        if submit:
            if _verify_admin_secret(pwd):
                st.session_state["c3_authed"] = True
                st.session_state["c3_authed_at"] = now
                st.session_state["c3_failed_attempts"] = 0
                st.session_state["c3_locked_until"] = 0.0
                st.success("Authenticated.")
                st.rerun()
            else:
                failed = int(st.session_state.get("c3_failed_attempts", 0)) + 1
                st.session_state["c3_failed_attempts"] = failed
                if failed >= max_attempts:
                    st.session_state["c3_failed_attempts"] = 0
                    st.session_state["c3_locked_until"] = now + lockout_seconds
                    st.error(f"Account temporarily locked for {lockout_seconds}s.")
                    st.stop()
                st.error("Invalid password.")
    st.stop()


def _guard_lamp(ok: bool, name: str) -> str:
    return f"{name} {'✅' if ok else '⚠️'}"


def _render_header(
    license_payload: Dict[str, Any],
    license_status: str,
    usage_db_path: Path,
    *,
    log_salt_loaded: bool,
    decision_health: Dict[str, Any],
    heartbeat: Dict[str, Any],
) -> None:
    customer_name = str(license_payload.get("customer_name", "Unknown Customer"))
    uid = str(license_payload.get("uid", license_payload.get("license_id", "N/A")))
    tier = _license_tier(license_payload)
    expiry_date = str(license_payload.get("expiry_date", ""))
    ttl_days = _license_days_left(expiry_date) if expiry_date else -1

    ttl_color = "green"
    if ttl_days < 0:
        ttl_color = "red"
    elif ttl_days <= 30:
        ttl_color = "orange"

    st.markdown("## 1) 身份與安全區")
    top_a, top_b, top_c = st.columns([2, 2, 3])
    top_a.metric("Customer", customer_name)
    top_a.caption(f"UID: `{uid}`")
    top_a.caption(f"Tier: **{tier}**")

    ttl_text = f"{ttl_days} Days Left" if ttl_days >= 0 else "invalid_expiry"
    top_b.markdown(f"**TTL 狀態：** :{ttl_color}[{ttl_text}]")
    top_b.caption(f"License status: `{license_status}`")

    health_ok = decision_health.get("status") in {"HEALTHY", "NO_TRAFFIC"}
    lamps = " / ".join(
        [
            _guard_lamp(log_salt_loaded, "SALT"),
            _guard_lamp(health_ok, "HEALTH"),
            _guard_lamp(bool(heartbeat.get("ok")), "HEARTBEAT"),
        ]
    )
    top_c.markdown("**Security Guards**")
    all_ok = log_salt_loaded and health_ok and bool(heartbeat.get("ok"))
    if all_ok:
        top_c.success(lamps)
    else:
        top_c.warning(lamps)
    top_c.caption(
        f"error_rate_24h={decision_health['error_rate_24h']:.2%} | "
        f"counter={heartbeat.get('heartbeat_counter', 0)}"
    )
    st.caption(f"usage.db: `{usage_db_path}`")


def main() -> None:
    st.set_page_config(page_title="Continuum Command Center", page_icon=":shield:", layout="wide")
    _render_login()

    usage_db_path = _default_usage_db_path()
    license_file = _default_license_file()
    license_key = os.environ.get("LICENSE_KEY", "").strip()
    signing_key = _signing_key()
    api_version = os.environ.get("API_VERSION", "1.1")
    log_salt_loaded = bool(os.environ.get("LOG_SALT", "").strip())

    license_payload, license_status = _load_license_payload(license_file, license_key)

    if not usage_db_path.exists():
        st.error(f"usage.db not found at {usage_db_path}")
        st.stop()

    with _connect_usage_db_readonly(usage_db_path) as conn:
        month_key = _today_utc().strftime("%Y-%m")
        counts = _fetch_monthly_counts(conn, month_key)
        trend_df = _fetch_decision_distribution_30d(conn)
        decision_health = _fetch_decision_health(conn)
        meta = _fetch_usage_meta(conn)
        heartbeat = _verify_heartbeat(meta, signing_key)

    _render_header(
        license_payload,
        license_status,
        usage_db_path,
        log_salt_loaded=log_salt_loaded,
        decision_health=decision_health,
        heartbeat=heartbeat,
    )

    quota_limit = _safe_int(license_payload.get("quota_limit"), 0)
    usage_count = counts["analysis_count"]
    progress = 0.0 if quota_limit <= 0 else min(1.0, usage_count / quota_limit)
    tier = _license_tier(license_payload)
    cost = _build_cost_estimate(tier=tier, usage_count=usage_count, quota_limit=quota_limit)

    st.markdown("## 2) 流量與收錢區")
    left, right = st.columns([2, 1])
    left.metric("當前消耗 / 授權總配額", f"{usage_count:,} / {quota_limit:,}" if quota_limit > 0 else f"{usage_count:,} / N/A")
    left.progress(progress)
    left.caption(f"0  ← 進度條 →  {quota_limit:,}" if quota_limit > 0 else "Quota not configured")

    if quota_limit > 0 and progress >= 0.85:
        left.warning("配額已超過 85%，進入收費提醒區間。")
    elif quota_limit > 0:
        left.success("配額尚在安全緩衝區。")
    else:
        left.info("未偵測到 quota_limit，無法計算配額緩衝。")

    right.metric("緩衝區消耗", f"{progress * 100:.1f}%" if quota_limit > 0 else "N/A")
    right.metric("Decision Health (24h)", decision_health["status"])
    right.metric("Heartbeat Guard", "OK" if heartbeat.get("ok") else f"ALERT:{heartbeat.get('reason')}")

    if trend_df.empty:
        st.info("過去 30 天尚無流量資料。")
    else:
        pivot = (
            trend_df.pivot_table(index="day", columns="decision_bucket", values="count", aggfunc="sum", fill_value=0)
            .sort_index()
        )
        for col in ["ALLOW", "GUIDE", "ERROR"]:
            if col not in pivot.columns:
                pivot[col] = 0
        pivot = pivot[["ALLOW", "GUIDE", "ERROR"]]
        st.markdown("**30 天流量趨勢（ALLOW / GUIDE / ERROR）**")
        st.line_chart(pivot)

    st.markdown("**成本估算器（階梯定價）**")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Base (USD/月)", f"{cost['base_monthly_usd']:.2f}")
    c2.metric("超額次數", str(cost["overage_count"]))
    c3.metric("超額費用 (USD)", f"{cost['overage_fee_usd']:.2f}")
    c4.metric("預估總成本 (USD)", f"{cost['projected_total_usd']:.2f}")

    st.divider()
    st.markdown("## 3) 指揮動作區")
    a1, a2, a3 = st.columns(3)

    with a1:
        if st.button("產出對帳加密檔", use_container_width=True):
            try:
                target, payload = _generate_evidence_summary_sig(
                    db_path=usage_db_path,
                    output_dir=APP_DIR / "logs" / "usage",
                    signing_key=signing_key,
                    license_payload=license_payload,
                )
                st.success(f"已產出：{target}")
                st.code(json.dumps(payload, ensure_ascii=False, indent=2), language="json")
            except Exception as exc:
                st.error(f"產出失敗：{exc}")

    with a2:
        if st.button("匯出合規報告", use_container_width=True):
            try:
                target, payload = _export_scrub_log(
                    db_path=usage_db_path,
                    output_dir=APP_DIR / "logs" / "exports",
                    api_version=api_version,
                )
                st.success(f"已匯出：{target}")
                st.caption(f"Record count: {payload['record_count']}")
            except Exception as exc:
                st.error(f"匯出失敗：{exc}")

    with a3:
        upload = st.file_uploader("上傳授權檔 (.key/.enc)", type=["key", "enc", "json"])
        if st.button("更新授權密鑰", use_container_width=True):
            if upload is None:
                st.warning("請先上傳授權檔。")
            else:
                try:
                    payload = _update_license_file(upload.read(), license_file=license_file, license_key=license_key)
                    st.success("授權更新成功。")
                    st.code(json.dumps(payload, ensure_ascii=False, indent=2), language="json")
                except Exception as exc:
                    st.error(f"更新失敗：{exc}")

    st.divider()
    if st.button("Logout"):
        st.session_state["c3_authed"] = False
        st.session_state["c3_authed_at"] = 0.0
        st.rerun()


if __name__ == "__main__":
    main()
