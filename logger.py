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

Optional env flags:
- GITHUB_BRANCH: branch to write to (default: "main")
- LOG_STORE_TEXT: "1" to store raw input text in logs (default: off, store hash only)
"""

from __future__ import annotations

import json
import os
import time
import uuid
import hashlib
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

import requests


def _utc_dates():
    now = datetime.utcnow()
    return (
        now.strftime("%Y-%m"),   # year_month
        now.strftime("%Y%m%d"),  # date_str
        now.strftime("%H%M%S"),  # time_str
    )


def _iso_utc_z() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _store_text_enabled() -> bool:
    return os.environ.get("LOG_STORE_TEXT", "").strip() == "1"


def _sha256(s: str) -> str:
    return hashlib.sha256((s or "").encode("utf-8")).hexdigest()


class GitHubWriter:
    """
    Minimal GitHub Contents API writer.
    Writes one file per event to avoid SHA conflicts.
    """

    def __init__(self):
        self.github_token = os.environ.get("GITHUB_TOKEN")
        self.github_repo = os.environ.get("GITHUB_REPO")  # owner/repo
        self.github_branch = os.environ.get("GITHUB_BRANCH", "main").strip() or "main"

        self.enabled = bool(self.github_token and self.github_repo)

        # Use stable headers to reduce GitHub API quirks
        self.headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "continuum-api-logger",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.github_token:
            # Fine-grained PAT compatible
            self.headers["Authorization"] = f"Bearer {self.github_token}"

    def _put_file(self, path: str, payload: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Create/overwrite a single file via PUT.
        Returns (ok, reason_code).
        """
        if not self.enabled:
            return False, "disabled"

        url = f"https://api.github.com/repos/{self.github_repo}/contents/{path}"

        content_bytes = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        b64 = __import__("base64").b64encode(content_bytes).decode("utf-8")

        data = {
            "message": f"Add log {payload.get('id', '')}".strip(),
            "content": b64,
            "branch": self.github_branch,
        }

        # small retry for transient errors (HF ↔ GitHub network / 429 / 5xx)
        retries = 2
        backoffs = [0.5, 1.0]

        for attempt in range(retries + 1):
            try:
                r = requests.put(url, headers=self.headers, json=data, timeout=15)

                if r.status_code in (200, 201):
                    return True, "ok"

                # Retry only on rate limit / server issues
                if r.status_code in (429, 500, 502, 503, 504) and attempt < retries:
                    time.sleep(backoffs[attempt] if attempt < len(backoffs) else 1.0)
                    continue

                # Non-retryable failure
                # Keep message short (do not break API)
                short = (r.text or "")[:200]
                print(f"[GitHubWriter] PUT failed {r.status_code}: {short}")
                return False, f"http_{r.status_code}"

            except Exception as e:
                print(f"[GitHubWriter] PUT exception: {e}")
                if attempt < retries:
                    time.sleep(backoffs[attempt] if attempt < len(backoffs) else 1.0)
                    continue
                return False, "exception"

        return False, "unknown"

    def write_event(self, category: str, event: Dict[str, Any], event_id: str) -> Tuple[bool, str]:
        """
        Write event as a unique file:
          logs/<YYYY-MM>/<YYYYMMDD>/<category>/<event_id>.json
        """
        year_month, date_str, _ = _utc_dates()
        path = f"logs/{year_month}/{date_str}/{category}/{event_id}.json"
        return self._put_file(path, event)


class DataLogger:
    """
    API-facing logger used by app.py.

    Methods:
    - log_analysis(input_text, output_result, metadata) -> dict
    - log_feedback(log_id, accuracy, helpful, accepted) -> dict
    - get_stats() -> dict
    """

    def __init__(self, log_dir: str = "logs"):
        self.log_dir = log_dir
        self.writer = GitHubWriter()

        # in-memory counters (safe minimal stats; persists only within runtime)
        self._analysis_count = 0
        self._feedback_count = 0
        self._last_analysis_ts: Optional[str] = None

        if self.writer.enabled:
            print(f"[DataLogger] GitHub logging enabled -> {os.environ.get('GITHUB_REPO')} ({self.writer.github_branch})")
        else:
            print("[DataLogger] GitHub credentials not set; logging will be local-only (in-memory stats).")

    @staticmethod
    def _new_id(prefix: str) -> str:
        # short, URL-safe
        return f"{prefix}_{uuid.uuid4().hex[:12]}"

    def log_analysis(
        self,
        input_text: str,
        output_result: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new analysis log event and (optionally) ship to GitHub.

        Returns:
          - log_id: event_id (stable identifier)
          - created_at: UTC timestamp
          - github_write: ok/failed/disabled
          - github_error: reason code (if failed)
        """
        ts = _iso_utc_z()
        event_id = self._new_id("a")

        # privacy-safe default: do not store raw text unless enabled
        if _store_text_enabled():
            input_obj = {
                "text": input_text,
                "text_length": len(input_text or ""),
                "text_hash": _sha256(input_text or ""),
            }
        else:
            input_obj = {
                "text": None,
                "text_length": len(input_text or ""),
                "text_hash": _sha256(input_text or ""),
            }

        payload = {
            "id": event_id,
            "timestamp": ts,
            "type": "analysis",
            "input": input_obj,
            "result": output_result,
            "metadata": metadata or {},
            "runtime": {
                "source": "hf_space",
                "service": "continuum-api",
                "service_version": os.environ.get("SERVICE_VERSION", ""),
            },
        }

        # Update minimal stats
        self._analysis_count += 1
        self._last_analysis_ts = ts

        github_write = "disabled"
        github_error = None

        if self.writer.enabled:
            ok, reason = self.writer.write_event(category="analysis", event=payload, event_id=event_id)
            github_write = "ok" if ok else "failed"
            github_error = None if ok else reason

        return {
            "log_id": event_id,
            "created_at": ts,
            "github_write": github_write,
            "github_error": github_error,
        }

    def log_feedback(self, log_id: str, accuracy: int, helpful: int, accepted: bool) -> Dict[str, Any]:
        ts = _iso_utc_z()
        event_id = self._new_id("f")

        payload = {
            "id": event_id,
            "timestamp": ts,
            "type": "feedback",
            "target_log_id": log_id,
            "feedback": {
                "accuracy": accuracy,
                "helpful": helpful,
                "accepted": accepted,
            },
            "runtime": {
                "source": "hf_space",
                "service": "continuum-api",
                "service_version": os.environ.get("SERVICE_VERSION", ""),
            },
        }

        self._feedback_count += 1

        github_write = "disabled"
        github_error = None

        if self.writer.enabled:
            ok, reason = self.writer.write_event(category="feedback", event=payload, event_id=event_id)
            github_write = "ok" if ok else "failed"
            github_error = None if ok else reason

        return {
            "status": "ok",
            "feedback_id": event_id,
            "created_at": ts,
            "github_write": github_write,
            "github_error": github_error,
        }

    def get_stats(self) -> Dict[str, Any]:
        """
        Minimal stats that never break.
        If you later want 'real stats from GitHub logs', we can add a separate scheduled job.
        """
        return {
            "logger": {
                "enabled": self.writer.enabled,
                "repo": os.environ.get("GITHUB_REPO") if self.writer.enabled else None,
                "branch": self.writer.github_branch if self.writer.enabled else None,
                "store_text": _store_text_enabled(),
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
        # Safe no-op: do not break startup
        print("[GitHubBackup] restore() skipped (no-op)")
        return