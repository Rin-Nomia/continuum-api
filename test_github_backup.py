#!/usr/bin/env python3
"""
GitHub logging smoke test (updated).

Purpose:
- Validate env var naming compatibility (GITHUB_* preferred, GH_* legacy)
- Verify DataLogger can emit one content-free analysis event
- Verify GitHubBackup compatibility hook is callable
"""

from __future__ import annotations

import os
import json
from datetime import datetime

from logger import DataLogger, GitHubBackup


def _env_first(*names: str) -> str:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


def run_smoke() -> int:
    token = _env_first("GITHUB_TOKEN", "GH_TOKEN")
    repo = _env_first("GITHUB_REPO", "GH_REPO")
    log_salt = os.environ.get("LOG_SALT", "").strip()

    print("=" * 60)
    print("Continuum GitHub Logger Smoke Test")
    print("=" * 60)
    print(f"GITHUB repo configured: {bool(repo)} ({repo or 'N/A'})")
    print(f"GITHUB token configured: {bool(token)}")
    print(f"LOG_SALT configured: {bool(log_salt)}")

    if not log_salt:
        print("❌ LOG_SALT 缺失，DataLogger 依設計會拒絕啟動。")
        return 1

    logger = DataLogger(log_dir="logs")

    evidence = {
        "schema_version": "1.0",
        "input_fp_sha256": "test_input_fp",
        "input_length": 10,
        "output_fp_sha256": "test_output_fp",
        "output_length": 10,
        "freq_type": "Unknown",
        "mode": "no-op",
        "scenario": "smoke_test",
        "confidence": {"final": 0.0, "classifier": 0.0},
        "metrics": {"decision_state": "ALLOW", "reason_code": "TONE_UNKNOWN", "latency_ms": 1},
        "audit": {"source": "smoke_test"},
        "llm_used": False,
        "cache_hit": False,
        "model": "",
        "usage": {},
        "output_source": "smoke_test",
        "api_version": "smoke",
        "pipeline_version_fingerprint": "smoke",
    }

    res = logger.log_analysis(
        input_text=None,
        output_result=evidence,
        metadata={"test": True, "ts": datetime.utcnow().isoformat() + "Z"},
    )
    print("✅ log_analysis success:", json.dumps(res, ensure_ascii=False))

    backup = GitHubBackup(log_dir="logs")
    backup.restore()
    print("✅ GitHubBackup.restore() success")

    stats = logger.get_stats()
    print("✅ logger stats:", json.dumps(stats, ensure_ascii=False))
    print("Smoke test completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_smoke())
