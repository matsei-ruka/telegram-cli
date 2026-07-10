from __future__ import annotations

import asyncio
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from telethon import TelegramClient, functions, types

from telegram_cli.config import BOTS_DIR
from telegram_cli.format import console

TOKEN_RE = re.compile(r"\b(\d{6,12}:[A-Za-z0-9_-]{20,})\b")


def _slug_alt(base: str, n: int) -> str:
    base = base.removesuffix("_bot").removesuffix("bot")
    if n == 1:
        return f"{base}_bot"
    if n == 2:
        return f"{base}bot"
    if n == 3:
        return f"{base}_tg_bot"
    return f"{base}_{n}_bot"


async def _wait_bf_reply(
    client: TelegramClient, bf: Any, after_id: int, timeout: float = 30.0
) -> types.Message:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        msgs = await client.get_messages(bf, limit=5)
        for m in msgs:
            if m.id > after_id and m.out is False:
                return m
        await asyncio.sleep(0.6)
    raise TimeoutError(f"No BotFather reply within {timeout}s")


async def _latest_bf_id(client: TelegramClient, bf: Any) -> int:
    msgs = await client.get_messages(bf, limit=1)
    return msgs[0].id if msgs else 0


async def create_via_botfather(
    client: TelegramClient,
    display_name: str,
    username: str,
    *,
    quiet: bool = False,
) -> dict:
    bf = await client.get_entity("BotFather")
    username = username.lstrip("@")
    if not username.lower().endswith("bot"):
        username = f"{username}_bot"

    candidates: list[str] = []
    for i in range(1, 8):
        c = _slug_alt(username, i)
        if c not in candidates:
            candidates.append(c)
    if username not in candidates:
        candidates.insert(0, username)

    tried: list[str] = []
    token = None
    final_username = None
    raw_success = None

    for cand in candidates:
        if cand in tried:
            continue
        tried.append(cand)
        if not quiet:
            console.print(f"[cyan]→[/] Trying @{cand} …")

        before = await _latest_bf_id(client, bf)
        await client.send_message(bf, "/newbot")
        m1 = await _wait_bf_reply(client, bf, before)
        if not quiet:
            console.print(f"  BF: {(m1.message or '')[:120]!r}")

        before = m1.id
        await client.send_message(bf, display_name)
        m2 = await _wait_bf_reply(client, bf, before)
        if not quiet:
            console.print(f"  BF: {(m2.message or '')[:160]!r}")

        before = m2.id
        await client.send_message(bf, cand)
        m3 = await _wait_bf_reply(client, bf, before, timeout=40)
        text = m3.message or ""
        if not quiet:
            console.print(f"  BF: {text[:220]!r}")

        tok = TOKEN_RE.search(text)
        if tok:
            token = tok.group(1)
            final_username = cand
            raw_success = text
            break

        lower = text.lower()
        if any(
            x in lower
            for x in (
                "already taken",
                "is already",
                "sorry",
                "occupied",
                "not available",
                "unacceptable",
                "invalid",
                "too long",
                "too short",
            )
        ):
            await client.send_message(bf, "/cancel")
            await asyncio.sleep(0.8)
            continue

        await client.send_message(bf, "/cancel")
        await asyncio.sleep(0.8)

    if not token or not final_username:
        raise RuntimeError(f"Could not create bot. Tried: {tried}")

    bot_entity = await client.get_entity(final_username)
    return {
        "display_name": display_name,
        "username": final_username,
        "username_at": f"@{final_username}",
        "token": token,
        "bot_id": bot_entity.id,
        "access_hash": bot_entity.access_hash,
        "botfather_message": raw_success,
        "tried_usernames": tried,
    }


async def set_bot_photo(
    client: TelegramClient, bot: types.User, photo_path: Path
) -> Any:
    photo_path = Path(photo_path)
    if not photo_path.is_file():
        raise FileNotFoundError(photo_path)
    uploaded = await client.upload_file(str(photo_path))
    return await client(
        functions.photos.UploadProfilePhotoRequest(
            file=uploaded,
            bot=types.InputUser(user_id=bot.id, access_hash=bot.access_hash),
        )
    )


async def set_bot_info(
    client: TelegramClient,
    bot: types.User,
    *,
    name: str | None = None,
    about: str | None = None,
    description: str | None = None,
    lang_code: str = "",
) -> None:
    kwargs: dict[str, Any] = {
        "bot": types.InputUser(user_id=bot.id, access_hash=bot.access_hash),
        "lang_code": lang_code,
    }
    if name is not None:
        kwargs["name"] = name[:64]
    if about is not None:
        kwargs["about"] = about[:70]
    if description is not None:
        kwargs["description"] = description[:512]
    await client(functions.bots.SetBotInfoRequest(**kwargs))


async def resolve_bot(client: TelegramClient, ref: str) -> types.User:
    ref = ref.lstrip("@")
    entity = await client.get_entity(ref)
    if not isinstance(entity, types.User) or not entity.bot:
        raise SystemExit(f"Not a bot: {ref}")
    return entity


def save_bot_credentials(info: dict, photo: str | None = None) -> Path:
    BOTS_DIR.mkdir(parents=True, exist_ok=True)
    uname = info["username"]
    out = {
        **info,
        "photo": photo,
        "created_at": info.get("created_at")
        or datetime.now(timezone.utc).isoformat(),
        "t_me": f"https://t.me/{uname}",
    }
    path = BOTS_DIR / f"{uname}.json"
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    env_path = BOTS_DIR / f"{uname}.env"
    env_path.write_text(
        f"TELEGRAM_BOT_TOKEN={info['token']}\n"
        f"TELEGRAM_BOT_USERNAME={info['username']}\n"
        f"TELEGRAM_BOT_ID={info['bot_id']}\n"
        f"TELEGRAM_BOT_NAME={info['display_name']}\n"
    )
    return path


async def botfather_send(client: TelegramClient, text: str) -> str:
    """Send raw text to @BotFather and return reply text."""
    bf = await client.get_entity("BotFather")
    before = await _latest_bf_id(client, bf)
    await client.send_message(bf, text)
    reply = await _wait_bf_reply(client, bf, before, timeout=40)
    return reply.message or ""
