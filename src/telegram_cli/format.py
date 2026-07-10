from __future__ import annotations

from datetime import datetime
from typing import Any

from rich.console import Console
from rich.table import Table
from telethon import types
from telethon.utils import get_display_name

console = Console()
err_console = Console(stderr=True)


def peer_label(entity: Any) -> str:
    if entity is None:
        return "?"
    if isinstance(entity, types.User):
        name = " ".join(x for x in (entity.first_name, entity.last_name) if x) or "User"
        uname = f" @{entity.username}" if entity.username else ""
        bot = " [bot]" if entity.bot else ""
        return f"{name}{uname}{bot} ({entity.id})"
    title = getattr(entity, "title", None) or "Chat"
    uname = getattr(entity, "username", None)
    suffix = f" @{uname}" if uname else ""
    return f"{title}{suffix} ({entity.id})"


def msg_preview(message: Any, width: int = 80) -> str:
    if message is None:
        return ""
    text = getattr(message, "message", None) or ""
    media = getattr(message, "media", None)
    if media:
        kind = type(media).__name__.replace("MessageMedia", "")
        text = f"[{kind}] {text}".strip()
    text = text.replace("\n", " ")
    if len(text) > width:
        return text[: width - 1] + "…"
    return text


def fmt_dt(dt: datetime | None) -> str:
    if not dt:
        return ""
    # Telethon dates are usually UTC-aware
    if dt.tzinfo is not None:
        dt = dt.astimezone()
    return dt.strftime("%Y-%m-%d %H:%M")


async def sender_label(client: Any, message: Any) -> str:
    """Resolve a readable sender for a message."""
    if message is None:
        return ""
    if getattr(message, "out", False):
        return "me"
    try:
        sender = message.sender
        if sender is None and client is not None:
            sender = await message.get_sender()
        if sender is not None:
            name = get_display_name(sender) or peer_label(sender).split(" (")[0]
            return name[:40]
    except Exception:
        pass
    sid = getattr(message, "sender_id", None)
    if sid is not None:
        return str(sid)
    return ""


async def print_messages(
    messages: list,
    peer_hint: str = "",
    *,
    client: Any = None,
) -> None:
    table = Table(
        title=f"Messages{f' — {peer_hint}' if peer_hint else ''}",
        show_lines=False,
    )
    table.add_column("ID", style="cyan", justify="right")
    table.add_column("Date", style="dim")
    table.add_column("From", max_width=28)
    table.add_column("Text")

    rows = [m for m in messages if m is not None and not isinstance(m, types.MessageEmpty)]
    for m in reversed(rows):
        sender = await sender_label(client, m)
        table.add_row(
            str(m.id),
            fmt_dt(getattr(m, "date", None)),
            sender,
            msg_preview(m, 100),
        )
    console.print(table)


def print_dialogs(rows: list[tuple]) -> None:
    table = Table(title="Dialogs")
    table.add_column("#", justify="right", style="dim")
    table.add_column("Unread", justify="right")
    table.add_column("Date", style="dim")
    table.add_column("Peer")
    table.add_column("Last")
    for i, (dlg, entity, last) in enumerate(rows, 1):
        unread = str(dlg.unread_count) if dlg.unread_count else ""
        table.add_row(
            str(i),
            unread,
            fmt_dt(getattr(last, "date", None) if last else None),
            peer_label(entity),
            msg_preview(last, 60) if last else "",
        )
    console.print(table)
