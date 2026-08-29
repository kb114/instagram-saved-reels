#!/usr/bin/env python3
"""Interactive onboarding wizard for instagram-saved-reels.

Guides the user through: research directory, isolated Python environment,
dependency install, local Whisper model, Instagram session, collection choice,
run preferences. Writes config.json so every other script runs zero-arg.

Isolation rule: Python packages are installed into a dedicated virtualenv at
<research-root>/.venv — never into the interpreter running this wizard (that
may be an agent's own runtime with pinned dependencies). The chosen
interpreter is recorded in config.json and used for model download, session
setup, and the dry-run test.

Run in a real terminal — it asks questions. `--check` is the non-interactive
status report. Credentials are never printed, logged, or written to config.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PIP_PACKAGES = ["instagrapi", "requests", "faster-whisper"]
PIP_MODULES = {"instagrapi": "instagrapi", "requests": "requests", "faster-whisper": "faster_whisper"}
WHISPER_MODEL_MARKER = "models--Systran--faster-whisper-base"


def default_root() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "instagram-saved-reels"
    return Path.home() / ".local" / "share" / "instagram-saved-reels"


def venv_python(venv: Path) -> Path:
    return venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def ask(prompt: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    answer = input(f"{prompt}{suffix}: ").strip()
    return answer or (default or "")


def ask_yn(prompt: str, default: bool = False) -> bool:
    hint = "Y/n" if default else "y/N"
    answer = input(f"{prompt} [{hint}]: ").strip().lower()
    if not answer:
        return default
    return answer.startswith("y")


def check_only_report(root: Path) -> None:
    print("\n== Environment check ==")
    print(f"  python           {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} (running wizard)")
    vp = venv_python(root / ".venv")
    if vp.is_file():
        out = subprocess.run(
            [str(vp), "-c", "import importlib.util,sys;"
             "print(sys.version.split()[0], "
             "' '.join(sorted(m for m,p in " + repr(PIP_MODULES) + ".items() if importlib.util.find_spec(p))))"],
            capture_output=True, text=True)
        print(f"  venv             {vp} -> {out.stdout.strip() or out.stderr.strip()}")
    else:
        print("  venv             missing")
    for binary in ("ffmpeg", "ffprobe", "yt-dlp"):
        rows = shutil.which(binary) or ("optional, missing" if binary == "yt-dlp" else "MISSING")
        print(f"  {binary:<16} {rows}")
    for label, path in (
        ("whisper-model", root / "models" / WHISPER_MODEL_MARKER),
        ("ig-session", root / "ig_session.json"),
        ("config.json", root / "config.json"),
    ):
        print(f"  {label:<16} {'found' if path.is_file() or path.is_dir() else 'missing'} ({path})")


def ensure_environment(root: Path) -> Path:
    """Return the interpreter that owns the pipeline's Python packages."""
    vp = venv_python(root / ".venv")
    if vp.is_file():
        probe = subprocess.run(
            [str(vp), "-c", "import instagrapi, requests, faster_whisper"],
            capture_output=True)
        if probe.returncode == 0:
            print(f"Isolated environment ready: {vp}")
            return vp
        print("Existing venv is missing packages; reinstalling into it.")
    else:
        print("The pipeline's Python packages go into an isolated virtualenv,")
        print(f"not the interpreter running this wizard ({sys.executable}).")
        print("This protects any host/agent runtime with pinned dependencies.")
        if not ask_yn(f"Create isolated environment at {root / '.venv'}?", default=True):
            print("Falling back to the current interpreter. It must not be a")
            print("shared/agent environment — version conflicts can break it.")
            if not ask_yn(f"Really install into {sys.executable}?"):
                raise SystemExit("Aborted. Re-run onboarding when ready.")
            subprocess.run([sys.executable, "-m", "pip", "install", *PIP_PACKAGES], check=False)
            return sys.executable
        subprocess.run([sys.executable, "-m", "venv", str(root / ".venv")], check=True)
    subprocess.run([str(vp), "-m", "pip", "install", "--upgrade", "pip"], check=False, capture_output=True)
    result = subprocess.run([str(vp), "-m", "pip", "install", *PIP_PACKAGES], check=False)
    if result.returncode != 0:
        raise SystemExit("pip install failed inside the virtualenv. See output above.")
    return vp


def ensure_binaries() -> None:
    missing = [b for b in ("ffmpeg", "ffprobe") if not shutil.which(b)]
    if missing:
        print(f"\nMissing system binaries: {', '.join(missing)}")
        print("Install FFmpeg with your OS package manager, then re-run onboarding.")
        print("  Windows: winget install Gyan.FFmpeg | macOS: brew install ffmpeg | Debian/Ubuntu: sudo apt install ffmpeg")
        raise SystemExit("ffmpeg/ffprobe required")
    if not shutil.which("yt-dlp"):
        print("Note: yt-dlp not found (only needed for single public-URL mode; optional).")


def ensure_model(root: Path, interpreter: Path) -> Path:
    model_dir = Path(ask("Local Whisper model directory", str(root / "models"))).expanduser().resolve()
    marker = model_dir / WHISPER_MODEL_MARKER
    if marker.is_dir():
        print(f"Whisper base model found at {model_dir}")
        return model_dir
    print(f"\nThe Whisper 'base' model is not under {model_dir}.")
    print("It downloads once (~150 MB) and then runs fully offline.")
    if ask_yn("Download it now?", default=True):
        subprocess.run(
            [str(interpreter), "-c",
             "from faster_whisper import WhisperModel; "
             f"WhisperModel('base', device='cpu', compute_type='int8', download_root=r'{model_dir}')"],
            check=False,
        )
    if not marker.is_dir():
        raise SystemExit("Model still missing. Re-run onboarding when downloaded.")
    return model_dir


def ensure_session(root: Path, interpreter: Path) -> Path:
    session_file = Path(ask("Instagram session file location", str(root / "ig_session.json"))).expanduser().resolve()
    if session_file.is_file():
        print("Existing session file found; verifying...")
        result = subprocess.run(
            [str(interpreter), str(SCRIPT_DIR / "ig_setup.py"), "--session-file", str(session_file), "--check-only"],
            check=False)
        if result.returncode == 0:
            return session_file
        print("Session invalid or expired.")
    print("\nLog in to Instagram. Credentials are prompted securely, never stored in config.")
    print("Tip: a dedicated account is recommended. The session file is full account access.")
    if not ask_yn(f"Create session at {session_file} now?", default=True):
        raise SystemExit("A session file is required. Re-run onboarding when ready.")
    result = subprocess.run(
        [str(interpreter), str(SCRIPT_DIR / "ig_setup.py"), "--session-file", str(session_file)],
        check=False)
    if result.returncode != 0:
        raise SystemExit("Login failed. Re-run onboarding to retry.")
    return session_file


def choose_collection(session_file: Path, interpreter: Path) -> tuple[str, str]:
    result = subprocess.run(
        [str(interpreter), str(SCRIPT_DIR / "ig_collections.py"), "--session-file", str(session_file), "--json"],
        capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise SystemExit(f"Could not list collections: {result.stderr.strip()}")
    collections = json.loads(result.stdout)
    if not collections:
        raise SystemExit("This account has no saved collections. Create one in Instagram first.")
    print("\nYour saved collections:")
    for i, c in enumerate(collections, 1):
        print(f"  {i}. {c['name']} ({c.get('media_count', '?')} items)")
    while True:
        pick = ask("Pick a collection (number or exact name)", "1")
        if pick.isdigit() and 1 <= int(pick) <= len(collections):
            chosen = collections[int(pick) - 1]
        else:
            chosen = next((c for c in collections if (c["name"] or "").lower() == pick.lower()), None)
        if chosen:
            return str(chosen["id"]), chosen["name"]
        print("No such collection; try again.")


def write_config(root: Path, values: dict) -> Path:
    path = root / "config.json"
    path.write_text(json.dumps(values, indent=2), encoding="utf-8")
    if os.name == "posix":
        os.chmod(path, 0o600)
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Interactive setup wizard for instagram-saved-reels.")
    parser.add_argument("--check", action="store_true", help="Non-interactive environment/status report")
    parser.add_argument("--research-root", type=Path, help="Skip the directory prompt")
    args = parser.parse_args()

    if args.check:
        check_only_report(args.research_root or default_root())
        return 0

    print("=" * 60)
    print("instagram-saved-reels — first-run setup")
    print("This wizard configures YOUR account. Nothing leaves this machine")
    print("except Instagram API reads and (optionally) the one-time model download.")
    print("=" * 60)

    print("\n[1/6] Research directory (media, state, reports live here)...")
    root = (args.research_root or Path(ask("Research root", str(default_root())))).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)

    print("\n[2/6] Isolated Python environment + dependencies...")
    interpreter = ensure_environment(root)
    ensure_binaries()

    print("\n[3/6] Local Whisper model...")
    model_dir = ensure_model(root, interpreter)

    print("\n[4/6] Instagram session...")
    session_file = ensure_session(root, interpreter)

    print("\n[5/6] Choose the saved collection to research...")
    collection_id, collection_name = choose_collection(session_file, interpreter)
    print(f"Selected: {collection_name} (id {collection_id})")

    print("\n[6/6] Run preferences...")
    max_new_raw = ask("Max new Reels to download per run", "10")
    max_new = int(max_new_raw) if max_new_raw.isdigit() and int(max_new_raw) >= 1 else 10

    config = {
        "python": str(interpreter),
        "session_file": str(session_file),
        "collection": collection_id,
        "collection_name": collection_name,
        "research_root": str(root),
        "model_dir": str(model_dir),
        "max_new": max_new,
    }
    config_path = write_config(root, config)
    print(f"\nConfig written: {config_path}")

    collect = f'"{interpreter}" "{SCRIPT_DIR / "collect_new_reels.py"}" --config "{config_path}"'
    print("\n== Setup complete ==")
    print(f"Collect new Reels:   {collect}")
    print(f"Analyze a run:       \"{interpreter}\" \"{SCRIPT_DIR / 'analyze_collection.py'}\" <run>/collection_manifest.json --out-dir <run>/analysis")
    print(f"Cron (3x/week 11:00): 0 11 * * 1,3,5  {collect}")
    print("Hermes: create a cronjob with this skill attached and the SKILL.md research workflow.")

    if ask_yn("\nRun a dry-run test now (lists new Reels, downloads nothing)?", default=True):
        subprocess.run(
            [str(interpreter), str(SCRIPT_DIR / "collect_new_reels.py"), "--config", str(config_path), "--dry-run"],
            check=False,
        )
    print("Onboarding finished.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
