# telegram-cli (`tg`)

Full-featured **Telegram user-account CLI** (MTProto / [Telethon](https://docs.telethon.dev/)): messages, media, contacts, groups/channels, and bot management via **@BotFather** plus native APIs (profile photo, about, description).

> **Developers / agents:** see [AGENTS.md](./AGENTS.md) for architecture, setup, security, and contribution rules.

## Setup

```bash
git clone https://github.com/matsei-ruka/telegram-cli.git
cd telegram-cli
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

cp .env.example .env
# Fill TELEGRAM_API_ID / TELEGRAM_API_HASH from https://my.telegram.org

tg login
tg whoami
```

## Comandi principali

### Auth / account
| Comando | Descrizione |
|---|---|
| `tg login` | Login telefono + codice (+ 2FA) |
| `tg logout` | Logout |
| `tg whoami` / `tg me` | Account corrente |
| `tg status` | Stato sessione |
| `tg resolve @user` | Risolvi username/id/link |

### Chat
| Comando | Descrizione |
|---|---|
| `tg dialogs` / `tg chat list` | Lista dialoghi |
| `tg chat info <peer>` | Dettagli chat/user |
| `tg chat read <peer>` | Segna come letto |
| `tg chat join <link\|@ch>` | Entra in canale/gruppo |
| `tg chat leave <peer>` | Esci |
| `tg chat create-group -t Title -u @a,@b` | Crea gruppo |
| `tg chat create-channel -t Title` | Crea canale |
| `tg chat mute <peer> [--hours N]` | Muta |

### Messaggi
| Comando | Descrizione |
|---|---|
| `tg send <peer> "testo"` | Invia testo |
| `tg send <peer> -f file.jpg -c "caption"` | Invia file |
| `tg history <peer> -n 50` | Cronologia |
| `tg msg reply <peer> <id> "…"` | Rispondi |
| `tg msg forward <src> <dst> 1,2,3` | Inoltra |
| `tg msg edit <peer> <id> "…"` | Modifica |
| `tg msg delete <peer> 1,2,3` | Elimina |
| `tg search "query" [-p peer]` | Cerca |
| `tg msg pin <peer> <id>` | Pin |
| `tg msg get <peer> <id>` | Singolo messaggio |
| `tg listen [-p peer]` | Stream messaggi in tempo reale |

### Media
| Comando | Descrizione |
|---|---|
| `tg media upload <peer> path [--caption]` | Upload |
| `tg media download <peer> <msg_id> [-o out]` | Download allegato |
| `tg media download-chat <peer> -n 20` | Scarica media recenti |

### Contatti / profilo
| Comando | Descrizione |
|---|---|
| `tg contacts list` | Contatti |
| `tg contacts search query` | Cerca utenti |
| `tg contacts add -p +39… -n Nome` | Aggiungi contatto |
| `tg profile set-name First Last` | Nome |
| `tg profile set-about "…"` | Bio |
| `tg profile set-photo pic.jpg` | Tua foto profilo |

### Bot (BotFather + MTProto)
| Comando | Descrizione |
|---|---|
| `tg bots create -n "Name" -u handle_bot [-p photo.jpg]` | Crea bot |
| `tg bots set-photo @bot photo.jpg` | Foto bot (API nativa) |
| `tg bots set-info @bot --about "…" -d "…"` | About / description |
| `tg bots list` | Bot owned + credenziali salvate |
| `tg bots token @bot` | Stampa token salvato |
| `tg bots father "/mybots"` | Messaggio raw a BotFather |
| `tg bots create-batch botfather_first_10.csv [--only 1]` | Batch da CSV |

Credenziali bot salvate in `bots/<username>.json` e `.env`.

### Avanzate
| Comando | Descrizione |
|---|---|
| `tg raw help.GetConfig` | Chiama metodo TL grezzo |

## Config

| Env | Default |
|---|---|
| `TELEGRAM_API_ID` / `TELEGRAM_API_HASH` | obbligatori |
| `TG_SESSION_DIR` | `./sessions` |
| `TG_SESSION_NAME` | `user` |
| `TG_BOTS_DIR` | `./bots` |
| `TG_DOWNLOAD_DIR` | `./downloads` |

## Esempi

```bash
tg dialogs -n 20
tg history @example_bot -n 10
tg send @example_bot "ciao"
tg send me -f ./photo.jpg -c "test"
tg bots set-photo example_bot first-10-20260709/content-creator/profile_photo/selected.jpg
tg bots create-batch first-10-20260709/botfather_first_10.csv --only 2
```
