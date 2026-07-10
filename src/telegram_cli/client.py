from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from telethon import TelegramClient

from telegram_cli.config import SESSION_DIR, SESSION_PATH, api_credentials


def build_client(session: str | None = None) -> TelegramClient:
    api_id, api_hash = api_credentials()
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    path = session or str(SESSION_PATH)
    return TelegramClient(path, api_id, api_hash)


@asynccontextmanager
async def authed_client(session: str | None = None) -> AsyncIterator[TelegramClient]:
    client = build_client(session)
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise SystemExit(
                "Not logged in. Run:  tg login\n"
                f"(session: {SESSION_PATH}.session)"
            )
        yield client
    finally:
        if client.is_connected():
            await client.disconnect()
