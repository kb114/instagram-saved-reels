# Instagrapi Session Setup

The collector authenticates with a **session file**, not stored passwords.
`ig_setup.py` performs one interactive login and dumps instagrapi's settings
JSON; later runs only load that file.

## First-time setup

```bash
python scripts/ig_setup.py --session-file ~/.config/reel-research/ig_session.json
```

- Username and password are prompted interactively and never echoed or logged.
- If the account has 2FA, the script asks for the current code.
- On POSIX the file is chmod 600 automatically. On Windows, keep it under your
  user profile and out of synced/shared folders.

## Check a session without logging in

```bash
python scripts/ig_setup.py --session-file <file> --check-only
# SESSION_OK username=<you> pk=<id>
```

## Challenges and lockouts

Instagram may answer a fresh login with a **challenge** (email/SMS confirm) or
temporarily block logins from a new machine/IP:

1. Open instagram.com in a browser, log in as the same account, complete any
   "Was this you?" / verification prompt.
2. Wait a few minutes, then re-run `ig_setup.py`.
3. If challenges repeat, log in from the same network the script runs on.

If the saved session expires or is revoked, `ig_collections.py` and
`collect_new_reels.py` exit with `Session invalid`; re-run `ig_setup.py`.

## Security rules

- The session file is **full account access**. Never commit it, paste it, or
  copy it into agent notes/logs.
- Prefer a dedicated account for research pipelines.
- Collection reads are read-only, but they are still API calls from your
  account: keep runs small (`--max-new`), keep the built-in delays, and do not
  run many collectors in parallel.
- Automated collection can conflict with Instagram's Terms of Service. You are
  responsible for using it within the rules that apply to your account. This
  pipeline is designed for *your own saved collection*, at low volume.
