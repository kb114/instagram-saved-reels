#!/usr/bin/env python3
"""Incremental collector for one saved Instagram collection.

Downloads only Reels not present in <research-root>/seen_pks.json. Each
non-empty run writes runs/<YYYYMMDD_HHMMSS>/collection_manifest.json plus
videos/. Read-only against the account; credentials live only in the session
file created by ig_setup.py.

Zero-arg mode: with no flags it reads config.json written by onboard.py
(--config, or ./reel-research/config.json, or the default research root).
CLI flags always override config values.

Prints NO_NEW_REELS and exits 0 when there is nothing new — schedulers should
treat that as a silent success.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path


def default_config_path() -> Path | None:
    env = os.environ.get("REEL_RESEARCH_CONFIG")
    candidates = [Path(env)] if env else []
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        candidates.append(base / "instagram-saved-reels" / "config.json")
    else:
        candidates.append(Path.home() / ".local" / "share" / "instagram-saved-reels" / "config.json")
    candidates.append(Path("./reel-research/config.json"))
    return next((c for c in candidates if c.is_file()), None)


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def load_client(session_file: Path):
    if not session_file.is_file():
        raise SystemExit(f"Session file missing: {session_file}. Run ig_setup.py or onboard.py first.")
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


def resolve_collection_id(client, selector: str) -> str:
    if selector.isdigit():
        return selector
    for c in client.collections():
        if (c.name or "").lower() == selector.lower():
            return str(c.id)
    raise SystemExit(f"Collection not found: {selector!r}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Incrementally collect new Reels from one saved collection.")
    parser.add_argument("--config", type=Path, help="config.json from onboard.py (auto-detected when omitted)")
    parser.add_argument("--session-file", type=Path)
    parser.add_argument("--collection", help="Collection id or exact name")
    parser.add_argument("--research-root", type=Path, help="Durable directory (seen_pks.json + runs/)")
    parser.add_argument("--max-new", type=int)
    parser.add_argument("--dry-run", action="store_true", help="List new Reels; download nothing; touch no state")
    args = parser.parse_args()

    config: dict = {}
    config_path = args.config or default_config_path()
    if config_path:
        config = json.loads(config_path.read_text(encoding="utf-8"))

    session_file = args.session_file or (Path(config["session_file"]) if config.get("session_file") else None)
    collection = args.collection or config.get("collection")
    root = args.research_root or (Path(config["research_root"]) if config.get("research_root") else None)
    max_new = args.max_new or int(config.get("max_new", 10))

    if not session_file or not collection or not root:
        raise SystemExit(
            "Need session file, collection, and research root — pass flags, "
            "or run onboard.py to write config.json."
        )
    if max_new < 1:
        raise SystemExit("--max-new must be >= 1")

    state_path = root / "seen_pks.json"
    seen = set(json.loads(state_path.read_text(encoding="utf-8"))) if state_path.is_file() else set()

    client = load_client(session_file)
    collection_id = resolve_collection_id(client, collection)
    items = client.collection_medias(collection_id, amount=100)
    reels = [i for i in items if i.media_type == 2 and i.product_type == "clips"]
    fresh = [i for i in reels if str(i.pk) not in seen][:max_new]

    print(f"collection_reels={len(reels)} seen={len(seen)} new={len(fresh)}", flush=True)
    if args.dry_run:
        for item in fresh:
            print(f"NEW pk={item.pk} code={item.code} taken_at={item.taken_at}", flush=True)
        return 0
    if not fresh:
        print("NO_NEW_REELS", flush=True)
        return 0

    run_dir = root / "runs" / datetime.now().strftime("%Y%m%d_%H%M%S")
    videos = run_dir / "videos"
    videos.mkdir(parents=True, exist_ok=False)
    manifest_path = run_dir / "collection_manifest.json"

    manifest: list[dict] = []
    for position, item in enumerate(fresh, 1):
        if not item.video_url:
            print(f"WARN skip pk={item.pk}: no video_url (source may be deleted)", flush=True)
            continue
        destination = videos / f"{position:02d}_{item.pk}.mp4"
        path = Path(client.video_download(item.pk, folder=videos))
        if path != destination:
            path.replace(destination)
        if not (destination.is_file() and destination.stat().st_size > 100_000):
            raise SystemExit(f"Unverified download for pk={item.pk}")
        manifest.append({
            "collection_position": position,
            "pk": str(item.pk),
            "code": item.code,
            "taken_at": item.taken_at.isoformat() if item.taken_at else None,
            "caption": item.caption_text or "",
            "permalink": f"https://instagram.com/reel/{item.code}" if item.code else "",
            "video_path": str(destination),
            "download_status": "downloaded_verified",
            "bytes": destination.stat().st_size,
        })
        write_json(manifest_path, manifest)
        print(f"{position:02d}/{len(fresh)} downloaded_verified {item.code}", flush=True)
        time.sleep(1.2)

    if not manifest:
        print("NO_NEW_REELS (all fresh items unavailable)", flush=True)
        return 0

    seen.update(row["pk"] for row in manifest)
    write_json(state_path, sorted(seen))
    print(f"COMPLETE manifest={manifest_path} new={len(manifest)} total_seen={len(seen)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
