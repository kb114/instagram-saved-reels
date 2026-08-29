#!/usr/bin/env python3
"""Batch-analyze local videos listed in a collection manifest.

Never logs into a platform, reads .env files, or sends audio/video outside
this machine. Reuses one local Whisper model across the manifest so long
collection research is practical on CPU. The model must already exist under
--model-dir (or REEL_WHISPER_MODEL_DIR); nothing is downloaded here.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from reel_frames import (
    extract_frame,
    load_local_model,
    probe,
    require_binary,
    resolve_model_dir,
    sample_plan,
    transcribe_locally,
)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def valid_completed(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    transcript = data.get("transcript_path")
    frames = data.get("frames") or []
    return bool(
        data.get("transcription_status") in {"local_whisper_base", "no_audio"}
        and frames
        and all(Path(row["path"]).is_file() for row in frames)
        and (transcript is None or Path(transcript).is_file())
    )


def analyze(record: dict, output: Path, ffmpeg: str, ffprobe: str, model, max_frames: int, width: int) -> dict:
    manifest_path = output / "manifest.json"
    if valid_completed(manifest_path):
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        return {
            "collection_position": record["collection_position"],
            "pk": record["pk"],
            "analysis_manifest": str(manifest_path),
            "status": "existing_verified",
            "frame_count": len(data["frames"]),
            "transcription_status": data["transcription_status"],
        }

    if output.exists() and any(output.iterdir()):
        raise SystemExit(f"Refusing incomplete analysis directory: {output}")
    output.mkdir(parents=True, exist_ok=False)
    video = Path(record["video_path"])
    if not video.is_file():
        raise SystemExit(f"Video missing for collection position {record['collection_position']}: {video}")

    metadata = probe(video, ffprobe)
    frames_dir = output / "frames"
    frames_dir.mkdir()
    frames = []
    for index, (label, timestamp) in enumerate(sample_plan(float(metadata["duration_seconds"]), max_frames), 1):
        image_path = frames_dir / f"{index:02d}_{label}_{timestamp:06.2f}s.jpg"
        extract_frame(video, image_path, timestamp, width, ffmpeg)
        frames.append({"label": label.split("_", 1)[0], "timestamp_seconds": timestamp, "path": str(image_path)})

    transcript_path, status = (None, "no_audio")
    if metadata["has_audio"]:
        transcript_path, status = transcribe_locally(video, output, ffmpeg, model=model)
    manifest = {
        "source": record.get("permalink", ""),
        "source_type": "user-authorized_saved_collection_local_video",
        "video_path": str(video),
        "metadata": metadata,
        "frames": frames,
        "audio_transcribed": transcript_path is not None,
        "transcription_status": status,
        "transcript_path": str(transcript_path) if transcript_path else None,
        "privacy": {
            "api_uploads": False,
            "env_or_dotenv_reads": False,
            "network_access": False,
            "model": "local faster-whisper base cpu/int8",
        },
    }
    write_json(manifest_path, manifest)
    return {
        "collection_position": record["collection_position"],
        "pk": record["pk"],
        "analysis_manifest": str(manifest_path),
        "status": "analyzed_verified",
        "frame_count": len(frames),
        "transcription_status": status,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch-analyze a bounded local Reel manifest.")
    parser.add_argument("collection_manifest", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--start", type=int, default=1, help="First collection position, inclusive")
    parser.add_argument("--end", type=int, help="Last collection position, inclusive")
    parser.add_argument("--max-frames", type=int, default=16)
    parser.add_argument("--width", type=int, default=768)
    parser.add_argument("--model-dir", help="Local faster-whisper model root (or REEL_WHISPER_MODEL_DIR; default ./models)")
    args = parser.parse_args()
    if not 4 <= args.max_frames <= 32:
        raise SystemExit("--max-frames must be between 4 and 32")
    if not 320 <= args.width <= 1536:
        raise SystemExit("--width must be between 320 and 1536")

    records = json.loads(args.collection_manifest.read_text(encoding="utf-8"))
    selected = [r for r in records if r["collection_position"] >= args.start and (args.end is None or r["collection_position"] <= args.end)]
    if not selected:
        raise SystemExit("No collection records in requested range")
    ffmpeg, ffprobe = require_binary("ffmpeg"), require_binary("ffprobe")
    model = load_local_model(resolve_model_dir(args.model_dir))
    results = []
    for record in selected:
        output = args.out_dir / f"{record['collection_position']:02d}_{record['pk']}"
        result = analyze(record, output, ffmpeg, ffprobe, model, args.max_frames, args.width)
        results.append(result)
        write_json(args.out_dir / "analysis_manifest.json", results)
        print(f"{record['collection_position']:02d}/{selected[-1]['collection_position']:02d} {result['status']} frames={result['frame_count']} pk={record['pk']}", flush=True)
    print(f"COMPLETE analysis={args.out_dir / 'analysis_manifest.json'} reels={len(results)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
