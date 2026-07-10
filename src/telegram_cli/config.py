from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


def _detect_project_root() -> Path:
    """Best-effort repo root (for loading .env next to pyproject).

    Does NOT control where sessions/bots are stored — see data_root().
    """
    pkg = Path(__file__).resolve().parent
    # Editable install: …/src/telegram_cli → repo root is parents[1]
    if pkg.parent.name == "src":
        candidate = pkg.parent.parent
        if (candidate / "pyproject.toml").is_file():
            return candidate

    # Walk up from cwd looking for this project
    for base in [Path.cwd(), *Path.cwd().parents]:
        pyproject = base / "pyproject.toml"
        if not pyproject.is_file():
            continue
        try:
            text = pyproject.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if "telegram-cli" in text or "telegram_cli" in text:
            return base

    return Path.cwd()


def data_root() -> Path:
    """Where sessions, bots credentials, and downloads live.

    Priority:
      1. TG_DATA_DIR
      2. current working directory (safe for pip install + local clone)
    """
    override = os.environ.get("TG_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return Path.cwd()


PROJECT_ROOT = _detect_project_root()

# Load env: cwd first, then project root (so local .env wins)
_loaded = False
for env_path in (Path.cwd() / ".env", PROJECT_ROOT / ".env"):
    if env_path.is_file():
        load_dotenv(env_path, override=False)
        _loaded = True
if not _loaded:
    load_dotenv()

_DATA = data_root()

SESSION_DIR = Path(
    os.environ.get("TG_SESSION_DIR", str(_DATA / "sessions"))
).expanduser()
SESSION_NAME = os.environ.get("TG_SESSION_NAME", "user")
SESSION_PATH = SESSION_DIR / SESSION_NAME

BOTS_DIR = Path(os.environ.get("TG_BOTS_DIR", str(_DATA / "bots"))).expanduser()
DOWNLOAD_DIR = Path(
    os.environ.get("TG_DOWNLOAD_DIR", str(_DATA / "downloads"))
).expanduser()

# Back-compat alias used in docs / older code
ROOT = PROJECT_ROOT


def api_credentials() -> tuple[int, str]:
    api_id = os.environ.get("TELEGRAM_API_ID") or os.environ.get("TG_API_ID")
    api_hash = os.environ.get("TELEGRAM_API_HASH") or os.environ.get("TG_API_HASH")
    if not api_id or not api_hash:
        raise SystemExit(
            "Missing TELEGRAM_API_ID / TELEGRAM_API_HASH.\n"
            "Set them in .env (from https://my.telegram.org)."
        )
    try:
        return int(api_id), api_hash
    except ValueError as e:
        raise SystemExit(f"TELEGRAM_API_ID must be an integer, got {api_id!r}") from e
