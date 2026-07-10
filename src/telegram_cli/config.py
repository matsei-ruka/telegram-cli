from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Project root = repo root (…/telegram-cli), not the package dir
PACKAGE_DIR = Path(__file__).resolve().parent
ROOT = PACKAGE_DIR.parent.parent
if not (ROOT / "sessions").exists() and (Path.cwd() / "sessions").exists():
    ROOT = Path.cwd()

# Prefer cwd .env, then project root
for env_path in (Path.cwd() / ".env", ROOT / ".env"):
    if env_path.is_file():
        load_dotenv(env_path)
        break
else:
    load_dotenv()

SESSION_DIR = Path(os.environ.get("TG_SESSION_DIR", ROOT / "sessions"))
SESSION_NAME = os.environ.get("TG_SESSION_NAME", "user")
SESSION_PATH = SESSION_DIR / SESSION_NAME

BOTS_DIR = Path(os.environ.get("TG_BOTS_DIR", ROOT / "bots"))
DOWNLOAD_DIR = Path(os.environ.get("TG_DOWNLOAD_DIR", ROOT / "downloads"))


def api_credentials() -> tuple[int, str]:
    api_id = os.environ.get("TELEGRAM_API_ID") or os.environ.get("TG_API_ID")
    api_hash = os.environ.get("TELEGRAM_API_HASH") or os.environ.get("TG_API_HASH")
    if not api_id or not api_hash:
        raise SystemExit(
            "Missing TELEGRAM_API_ID / TELEGRAM_API_HASH.\n"
            "Set them in .env (from https://my.telegram.org)."
        )
    return int(api_id), api_hash
