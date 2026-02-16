#!/usr/bin/env python3
"""
Generate C3 dashboard preview screenshot.

Output:
  assets/dashboard_preview.png
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import shutil
import signal
import sqlite3
import socket
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Tuple
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parent
ASSET_PATH = ROOT / "assets" / "dashboard_preview.png"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def _kdf(secret: str) -> bytes:
    return hashlib.sha256(secret.encode("utf-8")).digest()


def _keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < length:
        block = hashlib.sha256(key + nonce + counter.to_bytes(8, "big")).digest()
        out.extend(block)
        counter += 1
    return bytes(out[:length])


def _encrypt_payload(payload: dict, secret: str) -> dict:
    nonce = os.urandom(16)
    plain = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    key = _kdf(secret)
    ks = _keystream(key, nonce, len(plain))
    ciphertext = bytes(a ^ b for a, b in zip(plain, ks))
    sig = hmac.new(key, nonce + ciphertext, hashlib.sha256).hexdigest()
    return {
        "version": "1.0",
        "nonce_b64": base64.b64encode(nonce).decode("utf-8"),
        "ciphertext_b64": base64.b64encode(ciphertext).decode("utf-8"),
        "signature_hex": sig,
    }


def _heartbeat_sig(signing_key: str, total: int, counter: int, event_id: str, ts_utc: str) -> str:
    raw = f"{total}|{counter}|{event_id}|{ts_utc}".encode("utf-8")
    return hmac.new(signing_key.encode("utf-8"), raw, hashlib.sha256).hexdigest()


def _seed_usage_db(db_path: Path, signing_key: str) -> Tuple[int, str, str]:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE usage_events (
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
        conn.execute(
            """
            CREATE TABLE usage_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX idx_usage_events_month ON usage_events(month)")
        conn.execute("CREATE INDEX idx_usage_events_day ON usage_events(day)")
        conn.execute("CREATE INDEX idx_usage_events_day_decision ON usage_events(day, decision_state)")

        counter = 0
        now = _utc_now()
        last_event_id = ""
        last_ts = ""
        last_sig = ""

        for back in range(29, -1, -1):
            day = (now - timedelta(days=back)).date()
            day_key = day.isoformat()
            month_key = day_key[:7]
            for i in range(100):
                counter += 1
                event_id = f"pv_{counter:08d}"
                ts = datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc) + timedelta(seconds=i * 300)
                ts_utc = _utc_iso(ts)

                if i < 94:
                    decision = "ALLOW"
                    event_type = "analysis"
                    mode = "no-op"
                    reason = "ok"
                else:
                    decision = "GUIDE"
                    event_type = "analysis"
                    mode = "suggest"
                    reason = "tone_guard"

                sig = _heartbeat_sig(signing_key, counter, counter, event_id, ts_utc)
                conn.execute(
                    """
                    INSERT INTO usage_events(
                        event_id, event_type, ts_utc, month, day,
                        decision_state, mode, reason_code, llm_used, cache_hit,
                        latency_ms, heartbeat_counter, heartbeat_sig
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event_id,
                        event_type,
                        ts_utc,
                        month_key,
                        day_key,
                        decision,
                        mode,
                        reason,
                        0,
                        0,
                        65 if decision == "ALLOW" else 110,
                        counter,
                        sig,
                    ),
                )
                last_event_id = event_id
                last_ts = ts_utc
                last_sig = sig

        active_month = now.strftime("%Y-%m")
        meta = {
            "active_month": active_month,
            "total_events": str(counter),
            "heartbeat_counter": str(counter),
            "last_event_id": last_event_id,
            "last_event_ts": last_ts,
            "last_heartbeat_sig": last_sig,
        }
        for key, value in meta.items():
            conn.execute("INSERT INTO usage_meta(key, value) VALUES(?, ?)", (key, value))

        conn.commit()
        return counter, last_event_id, last_ts
    finally:
        conn.close()


def _wait_http_ready(url: str, timeout_seconds: int = 60) -> None:
    start = time.time()
    while time.time() - start < timeout_seconds:
        try:
            with urlopen(url, timeout=2) as resp:
                if 200 <= getattr(resp, "status", 200) < 500:
                    return
        except Exception:
            pass
        time.sleep(1.0)
    raise RuntimeError(f"timeout_waiting_for_streamlit:{url}")


def _pick_free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = int(s.getsockname()[1])
    s.close()
    return port


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        raise SystemExit(
            f"playwright_not_available:{exc}. Install with: python3 -m pip install playwright && python3 -m playwright install chromium"
        )

    tmp = Path(tempfile.mkdtemp(prefix="c3_preview_"))
    data_dir = tmp / "data"
    logs_dir = data_dir / "logs"
    license_dir = data_dir / "license"
    logs_dir.mkdir(parents=True, exist_ok=True)
    license_dir.mkdir(parents=True, exist_ok=True)

    usage_db = logs_dir / "usage.db"
    license_file = license_dir / "license.enc"

    log_salt = "preview-log-salt"
    signing_key = "preview-signing-key"
    license_key = "preview-license-key"
    admin_password = "PreviewAdmin#2026"

    _seed_usage_db(usage_db, signing_key)

    payload = {
        "license_id": "preview-001",
        "customer_name": "[待填充]",
        "uid": "UID-PREVIEW-0001",
        "tier": "LITE",
        "expiry_date": "2026-12-31",
        "quota_limit": 10_000_000,
    }
    license_file.write_text(
        json.dumps(_encrypt_payload(payload, license_key), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    env = dict(os.environ)
    env.update(
        {
            "LOG_SALT": log_salt,
            "USAGE_SIGNING_KEY": signing_key,
            "LICENSE_KEY": license_key,
            "LICENSE_FILE": str(license_file),
            "USAGE_DB_PATH": str(usage_db),
            "C3_ADMIN_PASSWORD": admin_password,
            "C3_LOGIN_MAX_ATTEMPTS": "5",
            "C3_LOCKOUT_SECONDS": "900",
            "C3_SESSION_TTL_SECONDS": "1800",
        }
    )

    preview_port = _pick_free_port()
    base_url = f"http://127.0.0.1:{preview_port}"

    cmd = [
        sys.executable,
        "manage.py",
        "dashboard",
        "--host",
        "127.0.0.1",
        "--port",
        str(preview_port),
    ]
    proc = subprocess.Popen(
        cmd,
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        _wait_http_ready(base_url)
        ASSET_PATH.parent.mkdir(parents=True, exist_ok=True)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1600, "height": 3200})
            page.goto(base_url, wait_until="networkidle")
            page.get_by_label("Admin Password").fill(admin_password)
            page.get_by_role("button", name="Login").click()
            page.wait_for_timeout(2000)
            page.screenshot(path=str(ASSET_PATH), full_page=True)
            browser.close()
    finally:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except Exception:
            pass
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except Exception:
                pass
            proc.wait(timeout=5)
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"preview_written:{ASSET_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
