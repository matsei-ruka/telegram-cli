"""Peer / message-id helpers used across CLI commands."""

from __future__ import annotations

import re
from typing import Any

import typer
from telethon import TelegramClient, types

_ID_RE = re.compile(r"^-?\d+$")


def normalize_peer(ref: str | int) -> str | int:
    """Normalize a CLI peer argument for Telethon get_entity.

    Numeric ids must be ints — get_entity("12345") fails, get_entity(12345) works.
    """
    if isinstance(ref, int):
        return ref
    s = str(ref).strip()
    if not s:
        raise typer.BadParameter("Empty peer")
    # bare numeric id (user / chat / channel id as Telethon expects)
    if _ID_RE.fullmatch(s):
        return int(s)
    return s


async def resolve_peer(client: TelegramClient, ref: str | int) -> Any:
    """Resolve @user, t.me link, phone, or numeric id to an entity."""
    return await client.get_entity(normalize_peer(ref))


def same_entity(a: Any, b: Any) -> bool:
    """Compare two entities by Telegram id."""
    aid = getattr(a, "id", None)
    bid = getattr(b, "id", None)
    return aid is not None and aid == bid


def parse_msg_ids(ids: str) -> list[int]:
    """Parse comma/space-separated message ids; raise BadParameter on junk."""
    parts = [x.strip() for x in re.split(r"[\s,]+", ids) if x.strip()]
    if not parts:
        raise typer.BadParameter("Provide at least one message id")
    out: list[int] = []
    for p in parts:
        if not _ID_RE.fullmatch(p):
            raise typer.BadParameter(f"Invalid message id: {p!r}")
        out.append(int(p))
    return out


def first_message(result: Any) -> Any | None:
    """send_file/send_message may return Message or list[Message]."""
    if result is None:
        return None
    if isinstance(result, list):
        return result[0] if result else None
    return result


def is_usable_message(msg: Any) -> bool:
    """True if msg is a real message (not empty/missing)."""
    if msg is None:
        return False
    if isinstance(msg, types.MessageEmpty):
        return False
    # Telethon custom Message always has id; MessageService is ok for display
    return hasattr(msg, "id")


def parse_mode_arg(parse: str | None) -> str | None:
    """Map CLI --parse to Telethon parse_mode (default plain text)."""
    if parse is None or parse in ("", "none", "off", "plain"):
        return None
    if parse in ("md", "markdown"):
        return "md"
    if parse == "html":
        return "html"
    raise typer.BadParameter("--parse must be one of: none, md, html")


def invite_hash_from_link(link: str) -> str | None:
    """Extract private invite hash from t.me/+HASH or t.me/joinchat/HASH.

    Returns None if the string does not look like a private invite.
    """
    s = link.strip()
    # Explicit invite forms only — do NOT treat bare "+" elsewhere as invite
    # (would break phones / random strings containing +).
    m = re.search(r"(?:t\.me/\+|telegram\.me/\+|joinchat/)([A-Za-z0-9_-]+)", s, re.I)
    if m:
        return m.group(1)
    # bare +HASH (Telegram share style). Exclude phone numbers (pure digits).
    if re.fullmatch(r"\+[A-Za-z0-9_-]{5,}", s):
        body = s[1:]
        if body.isdigit():
            return None
        return body
    return None
