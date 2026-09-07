# Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Session invalid` | expired/revoked session | re-run `ig_setup.py` |
| Login `ChallengeRequired` | new machine/IP | complete browser challenge, retry (see instagrapi-setup.md) |
| `Collection not found` | renamed collection | run `ig_collections.py` and use the printed id |
| `NO_NEW_REELS` but you just saved one | collection API lag | wait a few minutes; `--dry-run` to confirm |
| `no video_url` skip warning | source Reel deleted/unavailable | nothing to do; item stays out of state so a later run can retry if it reappears |
| `Local Whisper base model unavailable` | model never downloaded | run the one-time download command in SKILL.md, pass `--model-dir` |
| `Required binary missing: ffmpeg` | PATH not updated after install (common on Windows/winget) | restart the shell; on Windows the yt-dlp winget fallback is built in, ffmpeg is not — fix PATH |
| `transcription_status: no_audio` | silent/music Reel | analyze from frames; not an error |
| `ffmpeg failed at <t>s` near end | decode at final fractions | already mitigated (CTA stops ≤1s early); if still failing, re-run with fewer frames |
| `Refusing incomplete analysis directory` | previous run crashed mid-Reel | delete that one `NN_pk` directory, re-run; completed Reels resume fine |
| Empty transcript for talking video | quiet speech + VAD | re-run that Reel with `reel_frames.py --transcribe` and check `transcript.txt` |
| `vision_analyze` returns `HTTP 5xx`, timeout, or unavailable | vision provider/model is unavailable, malformed, or does not accept images | stop vision after the first failed probe for this run; continue with caption/transcript/source research; correct the dedicated vision route, then begin the next run with one representative-frame probe |
| Chat works but image analysis fails | text/coding endpoint inherited for vision | pin both a dedicated vision provider and an explicit image-capable model; do not assume a provider's coding endpoint accepts images |
| Kimi Coding rejects image input | Kimi Coding and Kimi Platform multimodal APIs are separate products | keep Kimi Coding for text work; configure the appropriate image-capable endpoint/model for vision instead |

## Rate limits

Symptoms: `429`, `Please wait a few minutes`, login challenges after many runs.
Response: stop, wait 30–60 minutes, reduce `--max-new`, keep runs to a few per
day. Never parallelize collectors.

## Vision failure guard

Vision is optional. Read the caption and local transcript first, then use at
most one sequential hook/CTA frame as a readiness probe if a material visual
detail remains unresolved. Do not parallelize vision before the probe succeeds.
If that probe fails, record the exact observed error and make no more vision
calls during the run. Continue verification from the transcript, caption, and
primary sources; mark evidence that exists only on screen as `unresolved`.
