#!/usr/bin/env python3
"""
Generate PBKDF2 hash for C3_ADMIN_PASSWORD_HASH.

Output format:
pbkdf2_sha256$<iterations>$<salt_b64>$<digest_hex>
"""

from __future__ import annotations

import argparse
import base64
import getpass
import hashlib
import os


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate C3 admin password hash")
    parser.add_argument("--password", default="", help="Plain password (optional, prompt if empty)")
    parser.add_argument("--iterations", type=int, default=260000)
    args = parser.parse_args()

    password = args.password or getpass.getpass("C3 admin password: ")
    if not password:
        raise SystemExit("password_required")

    salt_raw = os.urandom(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt_raw,
        int(args.iterations),
    ).hex()
    salt_b64 = base64.b64encode(salt_raw).decode("utf-8")
    print(f"pbkdf2_sha256${int(args.iterations)}${salt_b64}${digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
