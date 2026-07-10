from __future__ import annotations

from datetime import datetime
from typing import Any

from rich.console import Console
from rich.table import Table
from telethon import types

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
    text = message.message or ""
    if message.media:
        kind = type(message.media).__name__.replace("MessageMedia", "")
        text = f"[{kind}] {text}".strip()
    text = text.replace("\n", " ")
    if len(text) > width:
        return text[: width - 1] + "…"
    return text


def fmt_dt(dt: datetime | None) -> str:
    if not dt:
        return ""
    return dt.strftime("%Y-%m-%d %H:%M")


def print_messages(messages: list, peer_hint: str = "") -> None:
    table = Table(title=f"Messages{f' — {peer_hint}' if peer_hint else ''}", show_lines=False)
    table.add_column("ID", style="cyan", justify="right")
    table.add_column("Date", style="dim")
    table.add_column("From", max_width=28)
    table.add_column("Text")
    for m in reversed(list(messages)):
        sender = ""
        if m.sender:
            sender = peer_label(m.sender).split(" (")[0]
        elif m.out:
            sender = "me"
        table.add_row(str(m.id), fmt_dt(m.date), sender, msg_preview(m, 100))
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
