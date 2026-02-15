#!/usr/bin/env python3
"""
Simple management entrypoint for Continuum admin operations.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent


def run_dashboard(port: int, host: str) -> int:
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(APP_DIR / "c3_dashboard.py"),
        "--server.port",
        str(port),
        "--server.address",
        host,
        "--server.headless",
        "true",
    ]
    return subprocess.call(cmd, cwd=str(APP_DIR))


def main() -> int:
    parser = argparse.ArgumentParser(description="Continuum management CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    dash = sub.add_parser("dashboard", help="Run C3 dashboard on localhost")
    dash.add_argument("--port", type=int, default=8501)
    dash.add_argument("--host", default="127.0.0.1")

    args = parser.parse_args()

    if args.command == "dashboard":
        return run_dashboard(port=args.port, host=args.host)

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
