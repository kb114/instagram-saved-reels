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

## Rate limits

Symptoms: `429`, `Please wait a few minutes`, login challenges after many runs.
Response: stop, wait 30–60 minutes, reduce `--max-new`, keep runs to a few per
day. Never parallelize collectors.
