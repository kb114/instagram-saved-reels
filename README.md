# Instagram Saved Reels

Turn your saved Instagram Reels collection into a recurring, evidence-backed
capability-research pipeline for your AI agent.

```
collect new saves → local frames + local Whisper transcript → claim extraction
→ primary-source verification → safety gate → adopt / propose / reject
```

Built as a [Hermes Agent](https://github.com/NousResearch/hermes-agent) skill;
the scripts are plain Python and work standalone with any agent that can run
shell commands (Claude Code, Codex, Cursor, …).

## Why

AI-tool Reels are leads, not reviews. This pipeline collects what you saved,
analyzes it **fully locally** (frames + on-device Whisper transcription — no
audio uploads, no `.env` reads, no cookie scraping), then applies a strict
safety gate before anything gets near your agent's skills/plugins.

## Install

Copy this directory into your agent's skills folder, e.g. for Hermes:

```bash
# Hermes
hermes skills install https://github.com/kb114/instagram-saved-reels
# or clone into ~/.hermes/skills/research/instagram-saved-reels
```

## First run — interactive onboarding

```bash
python scripts/onboard.py
```

The wizard asks for your preferences and sets up everything for your account:

1. Research directory (media, state, reports)
2. Isolated Python virtualenv + dependencies — never touches the interpreter
   running the wizard (protects agent runtimes with pinned deps)
3. Local Whisper `base` model (one-time download, then fully offline)
4. Instagram login → local session file (secure prompt, 2FA/challenge support)
5. Pick the saved collection to watch
6. Run size + scheduler line

It writes `config.json`; afterwards everything runs zero-arg.

## Use

```bash
python scripts/collect_new_reels.py          # incremental; NO_NEW_REELS when empty
python scripts/analyze_collection.py runs/<ts>/collection_manifest.json --out-dir runs/<ts>/analysis
python scripts/reel_frames.py "<public-url-or-local-file>" --transcribe   # single video
```

Then have your agent read captions/manifests/transcripts and verify claims
against primary sources before calling vision. Vision is optional: when a
material on-screen name or visual claim remains unresolved, start with one
sequential hook/CTA-frame probe. Do not fan out vision calls before it succeeds;
on its first `HTTP 5xx`, timeout, unavailable, or non-success response, stop
vision for that run and continue with transcript/source evidence. Pin a dedicated
image-capable provider **and model**—a text/coding endpoint may reject images
even when the same provider has a separate multimodal API. Then apply
`references/safety-gate.md`:

- **Auto-adopt** only pure prompt/workflow skills (no scripts, env, network,
  subprocess, MCP/provider writes).
- **Everything else** is proposed to the human with the blocking reason.

## Privacy

- Session file = full account access; stays local, owner-only permissions.
- No audio/video uploads. Frames go to a vision model only when you explicitly
  analyze them.
- `yt-dlp` runs with `--ignore-config`, no cookies, public URLs only.

See `references/` for instagrapi setup, the safety gate, and troubleshooting.

## License

MIT — Omar Abdelaziz
