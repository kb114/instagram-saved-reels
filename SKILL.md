---
name: instagram-saved-reels
description: "Research saved Instagram Reels into verified agent upgrades."
version: 1.0.1
author: Omar Abdelaziz
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Instagram, Reels, Research, Vision, Skills, Security]
    category: research
privacy: local-first; session file stays local; no audio upload; no credential reading by analyzers
---

# Instagram Saved Reels

Turn a private Instagram saved collection into a recurring, evidence-backed
capability-research pipeline:

```
collect new saves → local frames + local Whisper transcript → claim extraction
→ primary-source verification → safety gate → adopt / propose / reject
```

## When to Use

- First run after installing: the user wants their saved-Reels research pipeline set up for THEIR account → run the onboarding wizard.
- Recurring "what did I save and is any of it a useful tool/skill/plugin" research.
- One-off analysis of a saved collection or a single public Reel / local video.
- Triaging AI-tool claims from social media before letting them near the agent.

Do not use it to bypass logins, scrape accounts the user does not control, or
repost private media.

## First run after installation — onboarding is MANDATORY

When a user invokes this skill for the first time (no `config.json` yet),
**do not improvise the setup**. Run the interactive wizard:

```bash
python scripts/onboard.py
```

- Agents: run it in a real terminal (`pty=true` / interactive shell). It asks
  the user questions — never answer them on the user's behalf.
- The wizard checks dependencies, offers to install missing pip packages,
  locates/downloads the local Whisper model, creates the Instagram session
  interactively, lets the user pick their saved collection, chooses the
  research directory and run size, writes `config.json`, prints their
  scheduler line, and offers a dry-run test.
- After onboarding, all scripts work with zero arguments via `config.json`.

To re-run only the environment check (non-interactive):

```bash
python scripts/onboard.py --check
```

## What the pipeline does

Everything media-related runs locally. The only network actions are the
Instagram collection read/download (via the user's own session file) and, in
single-Reel mode only, an explicit public-URL fetch.

## Requirements

| Dependency | Purpose | Install |
|---|---|---|
| Python 3.10+ | all scripts | — |
| `instagrapi`, `requests` | collection read/download | `pip install instagrapi requests` |
| `ffmpeg` + `ffprobe` | frames + audio extraction | OS package manager |
| `faster-whisper` | local transcription | `pip install faster-whisper` |
| `yt-dlp` (optional) | single public-URL mode only | `pip install yt-dlp` |

The wizard verifies all of these and offers fixes.

## Daily use (after onboarding)

```bash
python scripts/collect_new_reels.py            # incremental; prints NO_NEW_REELS when empty
python scripts/analyze_collection.py runs/<timestamp>/collection_manifest.json --out-dir runs/<timestamp>/analysis
```

- `seen_pks.json` at the research root makes runs incremental.
- `--dry-run` lists new Reels without touching state; `--max-new N` bounds runs.
- Overrides: `--session-file`, `--collection`, `--research-root`, `--model-dir`
  (or `REEL_WHISPER_MODEL_DIR`) beat `config.json` values.
- Single Reel / local video:

```bash
python scripts/reel_frames.py "<public-url-or-local-file>" --out-dir <dir> --transcribe
```

## Research + vision + adoption workflow (the agent's job)

For each Reel, read the manifest, caption, and local transcript before using
vision. Extract explicitly named tools/skills/plugins/projects and capability
claims from those sources first. Vision is optional evidence, not a prerequisite
for continuing the research.

1. **Gate vision before calling it** — use vision only when a material
   on-screen name, URL, UI detail, or visual claim remains unresolved after the
   caption/transcript review.
   - Configure a provider **and an explicit image-capable model**. Do not let a
     vision route inherit an arbitrary chat/coding model.
   - Start with exactly one representative hook or CTA frame, sequentially.
     Never fan out frame analysis before this probe succeeds.
   - If the probe succeeds, inspect only the additional named frames needed to
     answer the question, in bounded batches.
   - On the first `vision_analyze` non-success, HTTP 5xx, timeout, or
     unavailable response: make **zero** more vision calls in that run. Record
     `vision unavailable (<observed error>)`, continue with
     transcript/caption/primary-source evidence, and label visual-only claims
     `unresolved` rather than guessing.
2. **Verify** — find the primary source (official repo/docs). Label each claim
   `verified / partly verified / unsupported / misleading / unresolved`.
3. **Audit before any adoption** — shallow clone, read README/manifests, scan
   for: env/`.env` reads, network calls, subprocess, installers/postinstall
   hooks, cookie/session/OAuth handling, telemetry, external publishing.
4. **Gate** — apply `references/safety-gate.md`:
   - Auto-adopt ONLY pure prompt/workflow skills (a `SKILL.md` with no scripts,
     no env, no network, no subprocess, no MCP/provider writes).
   - Everything else: *proposed* with the blocking reason; the human decides.
5. **Record** — append dated findings (sources, verdicts, reasons) to a durable
   research log. Never record credential values.

## Scheduling

The wizard prints a ready cron line and, for Hermes users, the cronjob recipe.
`NO_NEW_REELS` exits make empty runs cheap. Example (3×/week, 11:00):

```
0 11 * * 1,3,5  cd <research-root> && python <skill-dir>/scripts/collect_new_reels.py && ...
```

## Privacy Boundary

- Session file and downloaded media stay on the user's machine. The session
  file is full account access — protect it like a password; the wizard stores
  it under the user profile with owner-only permissions on POSIX.
- Transcription is local `faster-whisper` (CPU/int8) with `local_files_only`;
  no audio is uploaded anywhere.
- The analyzers contain no login code, no `.env` reads, no network calls.
- `yt-dlp` runs with `--ignore-config` and no cookies, and only for a public
  URL the user explicitly passes to `reel_frames.py`.
- Frame images sent to a vision model leave the machine through that provider —
  explicit per call, never automatic.

## Pitfalls

- **Session challenges**: Instagram may require email/SMS verification after
  some logins. Re-run onboarding or `ig_setup.py`; see
  `references/instagrapi-setup.md`.
- **Rate limits**: keep `--max-new` small; 1.2s delay between downloads is
  built in. Never parallelize collection.
- **Silent/music Reels**: `transcription_status: no_audio` — frames only.
- **Final-frame decode**: CTA samples stop up to 1s before EOF on purpose.
- **Deleted Reels**: items with no `video_url` are skipped with a warning.
- **Vision error (`HTTP 5xx`, timeout, unavailable)**: this does not invalidate
  local frames or Whisper. Stop vision after the first failed probe for that
  run; continue from the caption, transcript, and primary sources. A later run
  may start with one new probe after the route is corrected.
- **Text-only route**: a provider's chat/coding endpoint can reject images even
  when that provider offers a separate multimodal product. Pin the dedicated
  vision provider and image-capable model. For example, do not send images to a
  Kimi Coding endpoint merely because another Kimi API supports vision.

## Verification

- `python scripts/onboard.py --check` prints dependency/session/model status.
- `python scripts/ig_setup.py --session-file <f> --check-only` verifies login.
- `collect_new_reels.py --dry-run` lists what would download; state unchanged.
- Every Reel manifest lists frame paths + transcript state; files must exist.
- A run is complete only when the analyzer prints `COMPLETE ... reels=N`.
- A vision-enabled run begins with at most one sequential probe; after a failed
  probe, its report contains the observed error and no later vision results.
