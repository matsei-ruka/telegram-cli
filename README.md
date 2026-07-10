# telegram-cli (`tg`)

Full-featured **Telegram user-account CLI** built on MTProto via [Telethon](https://docs.telethon.dev/).

Send and read messages, work with media, manage contacts and chats, create bots through **@BotFather**, and set bot profile photos / about text using **native MTProto APIs** (not available on the classic HTTP Bot API alone).

> **Developers and coding agents:** see [AGENTS.md](./AGENTS.md) for architecture, contribution rules, and security guidelines.

## Features

- User login session (`api_id` + `api_hash` + phone)
- Dialogs, history, send/reply/forward/edit/delete, search
- Unread inbox (`tg unread`) and live stream (`tg listen`)
- Media upload and download
- Contacts, profile, groups/channels
- Bot creation via BotFather, batch CSV support
- Bot photo and info updates as bot owner
- Saved bot credentials under `bots/`

## Requirements

- Python 3.11+
- Telegram API credentials from [my.telegram.org](https://my.telegram.org)

## Install

```bash
git clone https://github.com/matsei-ruka/telegram-cli.git
cd telegram-cli
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .

cp .env.example .env
# Set TELEGRAM_API_ID and TELEGRAM_API_HASH in .env

tg login
tg whoami
```

Console entry points after install: `tg`, `telegram-cli`, or `python -m telegram_cli`.

## Quick start

```bash
tg status
tg dialogs -n 20
tg unread
tg send me "hello from telegram-cli"
tg history me -n 5
tg bots list
```

## Commands

### Auth / account

| Command | Description |
|---|---|
| `tg login` | Interactive phone login (+ code, optional 2FA) |
| `tg logout` | Log out and remove local session |
| `tg whoami` / `tg me` | Show current account |
| `tg status` | Connection and session status |
| `tg resolve @user` | Resolve username, id, or link |

### Chats

| Command | Description |
|---|---|
| `tg dialogs` / `tg chat list` | List recent dialogs |
| `tg dialogs --unread` | Only chats with unread messages |
| `tg chat info <peer>` | Chat or user details |
| `tg chat read <peer>` | Mark chat as read |
| `tg chat join <link\|@channel>` | Join channel/group or invite |
| `tg chat leave <peer>` | Leave / delete dialog |
| `tg chat create-group -t Title -u @a,@b` | Create a basic group |
| `tg chat create-channel -t Title` | Create a channel (`--megagroup` for supergroup) |
| `tg chat mute <peer> [--hours N]` | Mute notifications |

### Messages

| Command | Description |
|---|---|
| `tg send <peer> "text"` | Send text |
| `tg send <peer> -f file.jpg -c "caption"` | Send file with caption |
| `tg history <peer> -n 50` | Message history |
| `tg unread` | Unread inbox (all chats or `--peer`) |
| `tg unread --mark-read` | Show unread and mark as read |
| `tg msg reply <peer> <id> "…"` | Reply |
| `tg msg forward <src> <dst> 1,2,3` | Forward messages |
| `tg msg edit <peer> <id> "…"` | Edit your message |
| `tg msg delete <peer> 1,2,3` | Delete messages |
| `tg search "query" [-p peer]` | Search globally or in one chat |
| `tg msg pin <peer> <id>` | Pin a message |
| `tg msg react <peer> <id> 👍` | React with emoji |
| `tg msg get <peer> <id>` | Fetch one message |
| `tg listen [-p peer]` | Stream new messages until Ctrl+C |

### Media

| Command | Description |
|---|---|
| `tg media upload <peer> path [--caption]` | Upload and send a file |
| `tg media download <peer> <msg_id> [-o out]` | Download attachment from a message |
| `tg media download-chat <peer> -n 20` | Download recent media from a chat |

### Contacts / profile

| Command | Description |
|---|---|
| `tg contacts list` | List contacts |
| `tg contacts search query` | Search users |
| `tg contacts add -p +1555… -n Name` | Import contact by phone |
| `tg contacts block <peer> [--unblock]` | Block or unblock |
| `tg profile set-name First Last` | Update display name |
| `tg profile set-about "…"` | Update bio |
| `tg profile set-photo pic.jpg` | Update your profile photo |

### Bots (BotFather + MTProto)

| Command | Description |
|---|---|
| `tg bots create -n "Name" -u handle_bot [-p photo.jpg]` | Create bot via @BotFather |
| `tg bots set-photo @bot photo.jpg` | Set bot profile photo (owner API) |
| `tg bots set-info @bot --about "…" -d "…"` | Set about / description |
| `tg bots list` | List owned bots + saved credentials |
| `tg bots token @bot` | Print saved token |
| `tg bots father "/mybots"` | Send a raw message to @BotFather |
| `tg bots create-batch bots.csv [--only 1]` | Create bots from a CSV batch |

Credentials are saved as `bots/<username>.json` and `bots/<username>.env` (gitignored).

### Advanced

| Command | Description |
|---|---|
| `tg raw help.GetConfig` | Call a raw TL method |

## Configuration

| Environment variable | Default | Notes |
|---|---|---|
| `TELEGRAM_API_ID` | — | Required |
| `TELEGRAM_API_HASH` | — | Required |
| `TG_API_ID` / `TG_API_HASH` | — | Aliases |
| `TG_SESSION_DIR` | `./sessions` | Session directory |
| `TG_SESSION_NAME` | `user` | Session file basename |
| `TG_BOTS_DIR` | `./bots` | Saved bot credentials |
| `TG_DOWNLOAD_DIR` | `./downloads` | Media downloads |

## Examples

```bash
# Inbox
tg unread
tg unread -p @BotFather
tg dialogs --unread

# Messaging
tg dialogs -n 20
tg history @username -n 10
tg send @username "hello"
tg send me -f ./photo.jpg -c "test upload"
tg listen -p @username

# Bots
tg bots create -n "My Helper" -u my_helper_demo_bot -p ./avatar.jpg
tg bots set-photo my_helper_demo_bot ./avatar.jpg
tg bots set-info my_helper_demo_bot --about "Demo bot" -d "Longer description"
tg bots token my_helper_demo_bot
```

## Security

**Never commit** `.env`, `sessions/`, or `bots/*.json` / `bots/*.env`.

- A session file is equivalent to full account access.
- A bot token is full control of that bot.

See [AGENTS.md](./AGENTS.md#security-non-negotiable) for the full policy.

## License

No license file is attached yet. Add one before redistributing if you need explicit terms.
