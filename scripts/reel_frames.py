#!/usr/bin/env python3
"""Bounded local frame samples (+ optional local transcript) for one video.

Privacy: a URL is passed only to yt-dlp with --ignore-config. This module has
no API client, never reads .env files or credentials, and never uses cookies,
browser profiles, plugins, or a shell. Transcription is local faster-whisper
with local_files_only — the model must already exist under --model-dir (or
REEL_WHISPER_MODEL_DIR); this script never downloads it.

Adapted from bradautomates/claude-video (MIT), hardened for local-only use.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".webm", ".mov", ".m4v", ".avi"}
DEFAULT_MODEL_DIR = Path("./models")


def resolve_model_dir(arg: str | None) -> Path:
    raw = arg or os.environ.get("REEL_WHISPER_MODEL_DIR") or str(DEFAULT_MODEL_DIR)
    return Path(raw).expanduser().resolve()


def find_binary(name: str) -> str | None:
    path = shutil.which(name)
    if path:
        return path
    if sys.platform == "win32":
        # winget updates PATH only for processes started after installation.
        local_app_data = Path.home() / "AppData" / "Local"
        packages = local_app_data / "Microsoft" / "WinGet" / "Packages"
        if name == "yt-dlp" and packages.is_dir():
            matches = sorted(packages.glob("yt-dlp.yt-dlp_*/yt-dlp.exe"))
            if matches:
                return str(matches[-1])
    return None


def require_binary(name: str) -> str:
    path = find_binary(name)
    if path:
        return path
    raise SystemExit(f"Required binary missing: {name}")


def is_public_url(source: str) -> bool:
    if source.startswith("-"):
        return False
    parsed = urlparse(source)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=False, capture_output=True, text=True)


def download_public_video(source: str, out_dir: Path, ytdlp: str) -> Path:
    download_dir = out_dir / "download"
    download_dir.mkdir(parents=True, exist_ok=True)
    output = str(download_dir / "source.%(ext)s")
    cmd = [
        ytdlp,
        "--ignore-config",
        "--no-playlist",
        "--no-warnings",
        "--no-progress",
        "--no-write-info-json",
        "--restrict-filenames",
        "-f", "bv*[height<=720]+ba/b[height<=720]/b",
        "--merge-output-format", "mp4",
        "-o", output,
        "--",
        source,
    ]
    result = run(cmd)
    candidates = sorted(
        path for path in download_dir.glob("source.*")
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
    )
    if result.returncode != 0 or not candidates:
        detail = (result.stderr or result.stdout).strip().splitlines()
        error = detail[-1] if detail else f"yt-dlp exit {result.returncode}"
        raise SystemExit(
            "Public video download failed. It may be removed, private, or login-required. "
            f"yt-dlp: {error}"
        )
    return candidates[0].resolve()


def resolve_video(source: str, out_dir: Path, ytdlp: str | None) -> tuple[Path, str]:
    if is_public_url(source):
        if not ytdlp:
            raise SystemExit("Required binary missing for public URLs: yt-dlp")
        return download_public_video(source, out_dir, ytdlp), "public_url"
    path = Path(source).expanduser().resolve()
    if not path.is_file():
        raise SystemExit(f"Local video not found: {path}")
    if path.suffix.lower() not in VIDEO_EXTENSIONS:
        raise SystemExit(f"Unsupported local video extension: {path.suffix}")
    return path, "local_file"


def probe(video: Path, ffprobe: str) -> dict:
    cmd = [
        ffprobe, "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(video),
    ]
    result = run(cmd)
    if result.returncode != 0:
        raise SystemExit(f"ffprobe failed: {result.stderr.strip()}")
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"ffprobe returned invalid JSON: {exc}") from exc
    streams = data.get("streams") or []
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    if not video_stream:
        raise SystemExit("No video stream found")
    duration = float((data.get("format") or {}).get("duration") or video_stream.get("duration") or 0)
    if duration <= 0:
        raise SystemExit("Could not determine video duration")
    return {
        "duration_seconds": round(duration, 3),
        "width": video_stream.get("width"),
        "height": video_stream.get("height"),
        "has_audio": any(s.get("codec_type") == "audio" for s in streams),
    }


def unique_points(values: list[float], duration: float) -> list[float]:
    # Fast ffmpeg seeking can emit no decoded frame in the final fractions of a
    # second. Reserve 10% (up to one second) at the tail for a reliable CTA
    # sample while keeping short Reels near their end.
    safe_last_frame = max(duration - min(1.0, duration * 0.1), 0.0)
    result: list[float] = []
    for value in values:
        point = round(min(max(value, 0.0), safe_last_frame), 2)
        if point not in result:
            result.append(point)
    return result


def sample_plan(duration: float, max_frames: int) -> list[tuple[str, float]]:
    hook = unique_points([0, 0.8, 1.8], duration)
    cta = unique_points([duration - 2.0, duration - 0.8, duration - 0.1], duration)
    reserved = unique_points(hook + cta, duration)
    timeline_count = max(0, max_frames - len(reserved))
    timeline = unique_points(
        [duration * (i + 1) / (timeline_count + 1) for i in range(timeline_count)],
        duration,
    ) if timeline_count else []
    plan: list[tuple[str, float]] = []
    for i, point in enumerate(hook):
        plan.append((f"hook_{i + 1:02d}", point))
    for i, point in enumerate(timeline):
        if point not in hook and point not in cta:
            plan.append((f"timeline_{i + 1:02d}", point))
    for i, point in enumerate(cta):
        if point not in hook:
            plan.append((f"cta_{i + 1:02d}", point))
    plan.sort(key=lambda item: item[1])
    return plan[:max_frames]


def extract_frame(video: Path, output: Path, timestamp: float, width: int, ffmpeg: str) -> None:
    scale = f"scale=min({width}\\,iw):-2:out_range=pc,format=yuvj420p"
    cmd = [
        ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
        "-ss", f"{timestamp:.2f}", "-i", str(video),
        "-frames:v", "1", "-vf", scale, "-q:v", "3", str(output),
    ]
    result = run(cmd)
    if result.returncode != 0 or not output.is_file() or output.stat().st_size == 0:
        raise SystemExit(f"ffmpeg failed at {timestamp:.2f}s: {result.stderr.strip()}")


def load_local_model(model_dir: Path):
    """Load the pre-installed model without network fallback."""
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise SystemExit("Local transcription unavailable: faster-whisper is not installed") from exc
    try:
        return WhisperModel(
            "base",
            device="cpu",
            compute_type="int8",
            download_root=str(model_dir),
            local_files_only=True,
        )
    except Exception as exc:
        raise SystemExit(
            f"Local Whisper base model unavailable under {model_dir}. Download it once with: "
            "python -c \"from faster_whisper import WhisperModel; "
            "WhisperModel('base', device='cpu', compute_type='int8', download_root='<model-dir>')\". "
            f"Model load error: {exc}"
        ) from exc


def transcribe_locally(video: Path, out_dir: Path, ffmpeg: str, model=None, model_dir: Path | None = None) -> tuple[Path | None, str]:
    """Write a timestamped transcript using the pre-installed local model only."""
    audio_path = out_dir / "audio.wav"
    audio_result = run([
        ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(video), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(audio_path),
    ])
    if audio_result.returncode != 0 or not audio_path.is_file():
        raise SystemExit(f"Local audio extraction failed: {audio_result.stderr.strip()}")

    if model is None:
        model = load_local_model(model_dir or DEFAULT_MODEL_DIR)

    segments, _info = model.transcribe(str(audio_path), beam_size=5, vad_filter=True)
    lines: list[str] = []
    for segment in segments:
        text = segment.text.strip()
        if text:
            lines.append(f"[{segment.start:06.2f}-{segment.end:06.2f}] {text}")
    transcript_path = out_dir / "transcript.txt"
    transcript_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return transcript_path, "local_whisper_base"


def prepare_output(path_arg: str | None) -> Path:
    if path_arg:
        out_dir = Path(path_arg).expanduser().resolve()
        if (out_dir / "manifest.json").exists():
            raise SystemExit(f"Refusing to overwrite existing manifest: {out_dir / 'manifest.json'}")
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir
    return Path(tempfile.mkdtemp(prefix="reel-frames-"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract bounded local frame samples for video analysis.")
    parser.add_argument("source", help="Explicit public URL or local video path")
    parser.add_argument("--out-dir", help="New or empty output directory")
    parser.add_argument("--max-frames", type=int, default=16)
    parser.add_argument("--width", type=int, default=768)
    parser.add_argument("--transcribe", action="store_true", help="Transcribe locally with the installed Whisper base model")
    parser.add_argument("--model-dir", help="Local faster-whisper model root (or REEL_WHISPER_MODEL_DIR; default ./models)")
    args = parser.parse_args()

    if not 4 <= args.max_frames <= 32:
        raise SystemExit("--max-frames must be between 4 and 32")
    if not 320 <= args.width <= 1536:
        raise SystemExit("--width must be between 320 and 1536")

    ffmpeg = require_binary("ffmpeg")
    ffprobe = require_binary("ffprobe")
    ytdlp = find_binary("yt-dlp")
    out_dir = prepare_output(args.out_dir)
    video, source_type = resolve_video(args.source, out_dir, ytdlp)
    metadata = probe(video, ffprobe)
    duration = float(metadata["duration_seconds"])
    plan = sample_plan(duration, args.max_frames)
    frames_dir = out_dir / "frames"
    frames_dir.mkdir(exist_ok=False)

    frames: list[dict] = []
    for index, (label, timestamp) in enumerate(plan, start=1):
        output = frames_dir / f"{index:02d}_{label}_{timestamp:06.2f}s.jpg"
        extract_frame(video, output, timestamp, args.width, ffmpeg)
        frames.append({
            "label": label.split("_", 1)[0],
            "timestamp_seconds": timestamp,
            "path": str(output),
        })

    transcript_path: Path | None = None
    transcription_status = "not_requested"
    if args.transcribe:
        if metadata["has_audio"]:
            transcript_path, transcription_status = transcribe_locally(
                video, out_dir, ffmpeg, model_dir=resolve_model_dir(args.model_dir)
            )
        else:
            transcription_status = "no_audio"

    manifest = {
        "source": args.source,
        "source_type": source_type,
        "video_path": str(video),
        "metadata": metadata,
        "frames": frames,
        "audio_transcribed": transcript_path is not None,
        "transcription_status": transcription_status,
        "transcript_path": str(transcript_path) if transcript_path else None,
        "privacy": {
            "public_url_behavior": "yt-dlp fetches only the explicit source URL without cookies or config",
            "api_uploads": False,
            "env_or_dotenv_reads": False,
        },
    }
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"manifest": str(manifest_path), "frame_count": len(frames)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
