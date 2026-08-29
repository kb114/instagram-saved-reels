#!/usr/bin/env python3
"""List saved collections, or resolve one collection name to its id.

Read-only. Loads the local session file created by ig_setup.py.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_client(session_file: Path):
    if not session_file.is_file():
        raise SystemExit(f"Session file missing: {session_file}. Run ig_setup.py first.")
    try:
        from instagrapi import Client
    except ImportError:
        raise SystemExit("instagrapi not installed. Run: pip install instagrapi")
    client = Client()
    client.delay_range = [2, 5]
    client.load_settings(str(session_file))
    try:
        client.account_info()
    except Exception as exc:
        raise SystemExit(f"Session invalid ({type(exc).__name__}). Re-run ig_setup.py.")
    return client


def main() -> int:
    parser = argparse.ArgumentParser(description="List or resolve Instagram saved collections.")
    parser.add_argument("--session-file", required=True, type=Path)
    parser.add_argument("--name", help="Exact collection name to resolve (case-insensitive)")
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    args = parser.parse_args()

    client = load_client(args.session_file)
    collections = client.collections()
    rows = [
        {"id": str(c.id), "name": c.name, "media_count": getattr(c, "media_count", None)}
        for c in collections
    ]

    if args.name:
        match = next((r for r in rows if (r["name"] or "").lower() == args.name.lower()), None)
        if not match:
            names = ", ".join(r["name"] or "?" for r in rows)
            raise SystemExit(f"Collection not found: {args.name!r}. Available: {names}")
        print(json.dumps(match) if args.json else f"{match['id']}\t{match['name']}\t{match['media_count']}")
        return 0

    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        for r in rows:
            print(f"{r['id']}\t{r['name']}\t{r['media_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
