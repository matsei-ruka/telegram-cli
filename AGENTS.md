# AGENTS.md — Developing telegram-cli

Instructions for humans and coding agents working on this repository.

## What this project is

**telegram-cli** (`tg`) is a full-featured **Telegram user-account CLI** built on [Telethon](https://docs.telethon.dev/) (MTProto), not the HTTP Bot API alone.

It can:

- Log in as a normal Telegram user (`api_id` + `api_hash` + phone session)
- Read/send messages, media, contacts, groups/channels
- Create bots via **@BotFather** automation
- Set bot profile photos and info via **native MTProto** (`photos.uploadProfilePhoto(bot=…)`, `bots.setBotInfo`)
- Save bot credentials under `bots/`
- Stream unread messages and live updates

Entry points (after install):

```bash
tg --help
telegram-cli --help
python -m telegram_cli --help
```

## Repository layout

```
telegram-cli/
├── AGENTS.md                 # This file
├── README.md                 # User-facing usage
├── pyproject.toml            # Package metadata, deps, console scripts
├── .env                      # LOCAL ONLY — never commit (api_id / api_hash)
├── .gitignore
├── create_bot.py             # Thin wrapper → `tg bots create`
├── verify_api.py             # Thin wrapper → `tg status` / login / bots list
├── src/telegram_cli/
│   ├── __init__.py           # Version
│   ├── __main__.py           # python -m telegram_cli
│   ├── cli.py                # Typer app: all commands
│   ├── client.py             # Telethon client factory + authed context
│   ├── config.py             # Paths, env loading
│   ├── botfather.py          # Bot create / photo / info helpers
│   └── format.py             # Rich tables / peer labels
├── sessions/                 # LOCAL ONLY — Telethon *.session files
├── bots/                     # LOCAL ONLY — saved bot tokens (*.json / *.env)
├── downloads/                # LOCAL ONLY — media downloads
└── (local only)              # agent batches / private assets — gitignored
```

### Module responsibilities

| Module | Role |
|--------|------|
| `cli.py` | All UX: Typer groups (`bots`, `chat`, `msg`, `media`, `contacts`, `profile`) and top-level aliases (`send`, `history`, `dialogs`, `unread`, `listen`) |
| `client.py` | `build_client()`, `authed_client()` — connect + require login |
| `config.py` | Resolve `ROOT`, `SESSION_PATH`, `BOTS_DIR`, `DOWNLOAD_DIR`, load `.env` |
| `botfather.py` | Conversational `/newbot` flow, username fallbacks, photo/info, credential persistence |
| `format.py` | Shared Rich console + table helpers |

Keep new features as:

1. Pure async helpers (in `botfather.py` or new modules under `src/telegram_cli/`), then
2. Thin Typer commands in `cli.py` that call `_run(async_fn())`.

Do **not** put large business logic inside Typer command bodies if it can be reused or tested.

## Prerequisites

- Python **3.11+**
- Telegram app credentials from [my.telegram.org](https://my.telegram.org) → **API development tools**
- Network access to Telegram DCs
- Optional: [GitHub CLI](https://cli.github.com/) (`gh`) for repo operations

## Setup (local)

```bash
git clone <repo-url>
cd telegram-cli
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .

cp .env.example .env        # if present; otherwise create .env manually
# Edit .env:
#   TELEGRAM_API_ID=…
#   TELEGRAM_API_HASH=…

tg login                    # phone + code (+ 2FA if enabled)
tg status
tg whoami
```

### Environment variables

| Variable | Required | Default | Meaning |
|----------|----------|---------|---------|
| `TELEGRAM_API_ID` | yes | — | App id from my.telegram.org |
| `TELEGRAM_API_HASH` | yes | — | App hash |
| `TG_API_ID` / `TG_API_HASH` | alt | — | Accepted aliases |
| `TG_SESSION_DIR` | no | `./sessions` | Directory for Telethon sessions |
| `TG_SESSION_NAME` | no | `user` | Session file basename |
| `TG_BOTS_DIR` | no | `./bots` | Where bot tokens JSON/env are stored |
| `TG_DOWNLOAD_DIR` | no | `./downloads` | Default media download root |

`config.py` loads `.env` from the current working directory first, then the project root.

**Data directories** (sessions, bots, downloads) default to **cwd** via `TG_DATA_DIR`, not the package install path — so a non-editable `pip install` does not write under `site-packages`.

Peer arguments that are pure integers are coerced with `peers.normalize_peer` before `get_entity` (Telethon rejects string ids like `"12345"`).

`tg chat leave` only leaves groups/channels. Use `tg chat delete-dialog` to remove private chats from the dialog list.

`tg unread` uses each dialog’s `read_inbox_max_id` so it shows messages newer than the last-read marker (not merely the last N messages).

## Architecture notes

### User session vs Bot API

- The CLI uses a **user** MTProto session (you are a normal account).
- Bot tokens from BotFather are for **HTTP Bot API** / bot runtimes elsewhere; this CLI stores them but primarily operates as the **owner user**.
- Setting a bot’s profile photo is **not** available on the classic Bot HTTP API; it works via MTProto as the owner:

  `photos.UploadProfilePhotoRequest(file=…, bot=InputUser(…))`

- Creating bots is done by chatting with `@BotFather` (`/newbot` → name → username) and parsing the token. Native `bots.createBot` exists for **managed bots** (requires a manager bot with `bot_can_manage_bots`); the default path is BotFather automation.

### Async + Typer

All Telethon calls are async. Commands wrap coroutines with:

```python
def _run(coro):
    return asyncio.run(coro)
```

Prefer one `asyncio.run` per CLI invocation. Do not nest event loops.

### Peer resolution

Almost every command accepts a **peer** string:

- `@username`
- numeric id
- `t.me/…` links (Telethon resolves many forms)
- special: `me` / Saved Messages often works via `get_entity("me")` depending on Telethon version — prefer explicit self from `get_me()` if `me` breaks

### Bot creation flow (`botfather.py`)

1. `/newbot`
2. Send display name
3. Send username (must end with `bot`)
4. On “taken / invalid”, `/cancel` and try alternate slugs (`namebot`, `name_tg_bot`, `name_2_bot`, …)
5. Regex-extract `digits:token` from BotFather’s success message
6. Resolve entity, optionally `set_bot_photo` / `set_bot_info`
7. Persist `bots/<username>.json` and `.env`

Batch mode: `tg bots create-batch path/to.csv [--only N]` expects columns like `botfather_newbot_name`, `botfather_username`, `botpic_path`, `botfather_about_text`, `botfather_description`, `order`, `bundle_slug`. Missing photo paths are resolved relative to the current working directory when possible.

### Unread / inbox

- `tg unread` — chats with `unread_count > 0`, optional message dump, optional `--mark-read`
- `tg dialogs --unread` — summary only
- `tg listen` — live `NewMessage` stream until Ctrl+C

## Command map (maintain this when adding features)

| Area | Commands |
|------|----------|
| Auth | `login`, `logout`, `whoami`/`me`, `status` |
| Resolve | `resolve` |
| Chat | `dialogs`, `chat list|info|read|join|leave|delete-dialog|create-group|create-channel|mute` |
| Messages | `send`, `history`, `search`, `listen`, `unread`, `msg reply|forward|edit|delete|pin|get|react` |
| Media | `media upload|download|download-chat` |
| Contacts | `contacts list|search|add|block` |
| Profile | `profile get|set-name|set-about|set-photo` |
| Bots | `bots create|set-photo|set-info|list|token|father|create-batch` |
| Advanced | `raw` (invoke TL methods by name) |

Top-level aliases exist for frequent ops (`send`, `history`, `dialogs`, `unread`, `listen`) so users need not always nest under `msg` / `chat`.

## Development workflow

### Install editable

```bash
pip install -e .
```

Changes under `src/telegram_cli/` are picked up without reinstall (pure Python).

### Run without install

```bash
PYTHONPATH=src python -m telegram_cli --help
```

### Smoke checks (manual)

Never commit real tokens. On a logged-in dev machine:

```bash
tg status
tg whoami
tg dialogs -n 5
tg send me "smoke test"
tg history me -n 3
tg unread -n 0
tg bots list
tg resolve @BotFather
```

Bot create/photo (destructive / rate-limited — use throwaway usernames):

```bash
tg bots create -n "Test Bot" -u some_unique_test_bot -p /path/to.jpg
tg bots set-photo some_unique_test_bot /path/to.jpg
tg bots set-info some_unique_test_bot --about "hi" -d "longer description"
```

### Code style

- Python 3.11+ type hints (`list[str]`, `X | None`)
- Prefer stdlib + Telethon + Typer + Rich + python-dotenv (keep deps minimal)
- User-facing strings can stay short; this doc and README are English
- Fail with clear `SystemExit` / Typer errors when not logged in or peer invalid
- Do not log full bot tokens in normal command output beyond explicit `tg bots token`

### Adding a new command

1. Implement async helper if non-trivial.
2. Register on the right Typer group in `cli.py`.
3. Use `authed_client()` unless the command is `login` / `status` / `logout`.
4. Document in `README.md` and update the command map in this file.
5. If it touches secrets or sessions, ensure `.gitignore` still covers outputs.

### Packaging

- Build backend: **hatchling**
- Console scripts: `tg` and `telegram-cli` → `telegram_cli.cli:app`
- Package lives under `src/telegram_cli` (src layout); wheel sources map to `telegram_cli`

```bash
pip install build
python -m build
```

## Security (non-negotiable)

**Never commit:**

- `.env` (api_id / api_hash)
- `sessions/**` (full account takeover)
- `bots/*.json`, `bots/*.env` (bot tokens = full bot control)
- Login codes, 2FA passwords, phone numbers in docs or issues

If secrets are ever committed, rotate Telegram app credentials / bot tokens immediately and purge git history.

Treat a leaked **user session file** as a full account compromise: revoke other sessions from Telegram Settings → Devices, delete local session, re-login.

Public repo policy: agent batch folders, persona bibles, and marketplace private assets are **gitignored** by default. Keep them local or in a private store. Do not put real bot usernames, tokens, or account identifiers in docs or examples.

## Testing strategy

There is no large automated suite yet. When adding tests:

- Prefer unit tests for pure helpers (username slug fallbacks, token regex, CSV row mapping) without network.
- Integration tests against live Telegram must be opt-in (`TG_LIVE_TEST=1`) and skipped in CI by default.
- Never assert on real production tokens or private chat contents in fixtures.

Suggested future layout:

```
tests/
  test_botfather_slugs.py
  test_config.py
  test_cli_help.py          # typer CliRunner --help only
```

## Common pitfalls

| Symptom | Likely cause |
|---------|----------------|
| `Missing TELEGRAM_API_ID` | No `.env` or wrong cwd |
| `Not logged in` | Run `tg login`; session path differs (`TG_SESSION_DIR`) |
| BotFather timeout | Flood / slow reply; retry; avoid parallel `/newbot` storms |
| Username taken | `create_via_botfather` tries alternates; check `tried_usernames` in saved JSON |
| Photo set fails | Not owner (`bot_can_edit`), invalid image, or stale `access_hash` — re-`get_entity` |
| `CreateChatRequest` errors | Telegram API churn; prefer documented Telethon helpers |
| Hatch / import errors | Install with `pip install -e .` from repo root |

## Git & release notes for agents

- Default branch: `main`
- Prefer small, focused commits
- Do not force-push `main` unless explicitly requested
- Do not commit secrets even if the user says “push everything” — exclude via `.gitignore` and mention what was omitted
- Version is in `src/telegram_cli/__init__.py` and `pyproject.toml` (keep in sync on release)

## Related Telegram docs

- [MTProto bots overview](https://core.telegram.org/api/bots)
- [Edit bot information (name, about, photo)](https://core.telegram.org/api/bots/info)
- [Managed bots / createBot](https://core.telegram.org/api/bots/managed-bots)
- [Telethon documentation](https://docs.telethon.dev/)

## Quick “definition of done” for a feature PR

- [ ] Works via `tg …` after `pip install -e .`
- [ ] Uses `authed_client()` or documents why not
- [ ] No secrets written outside `sessions/` / `bots/` / `downloads/`
- [ ] README + this AGENTS.md command map updated if user-visible
- [ ] Manual smoke path listed in the PR description
