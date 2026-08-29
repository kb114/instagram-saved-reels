#!/usr/bin/env python3
"""Create or verify a local Instagram session file for instagrapi.

Security contract:
- Prompts for credentials interactively (never accepted as CLI args, never
  logged, never echoed).
- Writes ONLY the instagrapi session settings JSON to --session-file.
- Sets owner-only permissions (0600) on POSIX.
- --check-only loads the existing session and prints the username; it never
  performs a fresh login.

A session file is full account access. Protect it like a password.
"""
from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path


def _restrict_permissions(path: Path) -> None:
    if os.name == "posix":
        os.chmod(path, 0o600)


def _new_client():
    try:
        from instagrapi import Client
    except ImportError:
        raise SystemExit("instagrapi not installed. Run: pip install instagrapi")
    client = Client()
    client.delay_range = [2, 5]
    return client


def check_only(session_file: Path) -> int:
    if not session_file.is_file():
        raise SystemExit(f"Session file missing: {session_file}")
    client = _new_client()
    client.load_settings(str(session_file))
    try:
        info = client.account_info()
    except Exception as exc:
        raise SystemExit(
            f"Session invalid or expired ({type(exc).__name__}). "
            "Re-run without --check-only to log in again."
        )
    print(f"SESSION_OK username={info.username} pk={info.pk}")
    return 0


def login(session_file: Path) -> int:
    client = _new_client()
    if session_file.is_file():
        client.load_settings(str(session_file))
        try:
            info = client.account_info()
            print(f"SESSION_REUSED username={info.username} pk={info.pk}")
            return 0
        except Exception:
            print("Existing session invalid; falling back to fresh login.", file=sys.stderr)

    username = input("Instagram username: ").strip()
    if not username:
        raise SystemExit("Username required")
    password = getpass.getpass("Instagram password (not echoed): ")
    if not password:
        raise SystemExit("Password required")

    try:
        client.login(username, password)
    except Exception as exc:
        name = type(exc).__name__
        if "TwoFactor" in name:
            code = input("2FA code: ").strip()
            client.login(username, password, verification_code=code)
        elif "Challenge" in name:
            raise SystemExit(
                "Instagram issued a login challenge. Open instagram.com in a browser, "
                "complete the challenge for this account, then re-run this script. "
                "See references/instagrapi-setup.md."
            )
        else:
            raise SystemExit(f"Login failed ({name}): {exc}")

    info = client.account_info()
    session_file.parent.mkdir(parents=True, exist_ok=True)
    client.dump_settings(str(session_file))
    _restrict_permissions(session_file)
    print(f"SESSION_CREATED username={info.username} pk={info.pk} file={session_file}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Create/verify a local instagrapi session file.")
    parser.add_argument("--session-file", required=True, type=Path)
    parser.add_argument("--check-only", action="store_true", help="Verify existing session; never log in")
    args = parser.parse_args()
    if args.check_only:
        return check_only(args.session_file)
    return login(args.session_file)


if __name__ == "__main__":
    raise SystemExit(main())
