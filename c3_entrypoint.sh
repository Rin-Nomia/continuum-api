#!/usr/bin/env sh
set -eu

if [ -z "${C3_ADMIN_PASSWORD_HASH:-}" ] && [ -z "${C3_ADMIN_PASSWORD:-}" ]; then
  echo "C3_ADMIN_PASSWORD_HASH or C3_ADMIN_PASSWORD is required" >&2
  exit 1
fi

if [ -n "${C3_ADMIN_PASSWORD:-}" ] && [ -z "${C3_ADMIN_PASSWORD_HASH:-}" ]; then
python3 - <<'PY'
import os
import re
import sys

pwd = os.environ.get("C3_ADMIN_PASSWORD", "")
checks = [
    (len(pwd) >= 12, "length>=12"),
    (bool(re.search(r"[A-Z]", pwd)), "uppercase"),
    (bool(re.search(r"[a-z]", pwd)), "lowercase"),
    (bool(re.search(r"[0-9]", pwd)), "digit"),
    (bool(re.search(r"[^A-Za-z0-9]", pwd)), "symbol"),
]
missing = [name for ok, name in checks if not ok]
if missing:
    sys.stderr.write(f"Weak C3_ADMIN_PASSWORD, missing: {', '.join(missing)}\n")
    sys.exit(1)
PY
fi

exec python3 manage.py dashboard --host "${C3_BIND_HOST:-0.0.0.0}" --port "${C3_PORT:-8501}"
