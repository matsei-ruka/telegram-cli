from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Annotated, Any, Optional

import typer
from rich.table import Table
from telethon import functions, types
from telethon.errors import RPCError
from telethon.tl.custom import Message
from telethon.utils import get_display_name

from telegram_cli import __version__
from telegram_cli.botfather import (
    botfather_send,
    create_via_botfather,
    resolve_bot,
    save_bot_credentials,
    set_bot_info,
    set_bot_photo,
)
from telegram_cli.client import authed_client, build_client
from telegram_cli.config import BOTS_DIR, DOWNLOAD_DIR, SESSION_PATH, api_credentials
from telegram_cli.format import console, peer_label, print_dialogs, print_messages
from telegram_cli.peers import (
    first_message,
    invite_hash_from_link,
    is_usable_message,
    parse_mode_arg,
    parse_msg_ids,
    resolve_peer,
    same_entity,
)

app = typer.Typer(
    name="tg",
    help="Full-featured Telegram CLI (user account via MTProto).",
    no_args_is_help=True,
    rich_markup_mode="rich",
    add_completion=False,
)

bots_app = typer.Typer(help="Create and manage bots (BotFather + MTProto).")
chat_app = typer.Typer(help="Dialogs, groups, channels.")
msg_app = typer.Typer(help="Send, read, edit, delete, search messages.")
media_app = typer.Typer(help="Upload / download attachments.")
contacts_app = typer.Typer(help="Contacts and user lookup.")
profile_app = typer.Typer(help="Your profile.")
app.add_typer(bots_app, name="bots")
app.add_typer(chat_app, name="chat")
app.add_typer(msg_app, name="msg")
app.add_typer(media_app, name="media")
app.add_typer(contacts_app, name="contacts")
app.add_typer(profile_app, name="profile")


def _run(coro):
    return asyncio.run(coro)


# ── meta ────────────────────────────────────────────────────────────────────


@app.callback()
def main_callback(
    version: Annotated[
        bool, typer.Option("--version", help="Show version and exit.")
    ] = False,
) -> None:
    if version:
        console.print(f"telegram-cli {__version__}")
        raise typer.Exit()


@app.command("version")
def version_cmd() -> None:
    """Show version."""
    console.print(f"telegram-cli {__version__}")


# ── auth ────────────────────────────────────────────────────────────────────


@app.command("login")
def login(
    phone: Annotated[
        Optional[str], typer.Option("--phone", "-p", help="Phone with country code")
    ] = None,
) -> None:
    """Interactive login (phone + code + optional 2FA)."""

    async def _login() -> None:
        client = build_client()
        await client.connect()
        try:
            if await client.is_user_authorized():
                me = await client.get_me()
                console.print(f"[green]Already logged in[/] as {peer_label(me)}")
                return

            ph = phone or typer.prompt("Phone (+39… / +44…)")
            await client.send_code_request(ph)
            code = typer.prompt("Code from Telegram")
            try:
                from telethon.errors import SessionPasswordNeededError

                await client.sign_in(phone=ph, code=code)
            except SessionPasswordNeededError:
                pw = typer.prompt("2FA password", hide_input=True)
                await client.sign_in(password=pw)

            me = await client.get_me()
            console.print(f"[green]Login OK[/] {peer_label(me)}")
            console.print(f"Session: {SESSION_PATH}.session")
        finally:
            if client.is_connected():
                await client.disconnect()

    _run(_login())


@app.command("logout")
def logout(
    force: Annotated[
        bool, typer.Option("--force", help="Delete local session only (no server logout)")
    ] = False,
) -> None:
    """Log out and remove local session."""

    async def _logout() -> None:
        client = build_client()
        await client.connect()
        try:
            if await client.is_user_authorized() and not force:
                await client.log_out()
                console.print("[green]Logged out from Telegram[/]")
        finally:
            if client.is_connected():
                await client.disconnect()

        for p in (
            Path(f"{SESSION_PATH}.session"),
            Path(f"{SESSION_PATH}.session-journal"),
        ):
            if p.exists():
                p.unlink()
                console.print(f"Removed {p}")

    _run(_logout())


@app.command("whoami")
@app.command("me")
def whoami() -> None:
    """Show the logged-in account."""

    async def _me() -> None:
        async with authed_client() as client:
            me = await client.get_me()
            full = await client(functions.users.GetFullUserRequest(me))
            console.print(f"[bold]{peer_label(me)}[/]")
            console.print(f"  phone:  {me.phone or '—'}")
            about = getattr(full.full_user, "about", None) or "—"
            console.print(f"  about:  {about}")
            console.print(f"  premium: {bool(me.premium)}")
            console.print(f"  session: {SESSION_PATH}.session")

    _run(_me())


@app.command("status")
def status() -> None:
    """Connection / auth status."""

    async def _status() -> None:
        try:
            api_id, _ = api_credentials()
            creds = f"api_id={api_id}"
        except SystemExit as e:
            msg = e.args[0] if e.args else str(e)
            console.print(f"[red]creds:[/] {msg}")
            return

        client = build_client()
        await client.connect()
        try:
            auth = await client.is_user_authorized()
            console.print(f"connected: {client.is_connected()}")
            console.print(f"authorized: {auth}")
            console.print(f"credentials: {creds}")
            console.print(f"session: {SESSION_PATH}.session")
            if auth:
                me = await client.get_me()
                console.print(f"user: {peer_label(me)}")
        finally:
            if client.is_connected():
                await client.disconnect()

    _run(_status())


# ── resolve helper ──────────────────────────────────────────────────────────


@app.command("resolve")
def resolve(
    peer: Annotated[str, typer.Argument(help="@user, t.me link, phone, or numeric id")],
) -> None:
    """Resolve a username / id / link to an entity."""

    async def _resolve() -> None:
        async with authed_client() as client:
            entity = await resolve_peer(client, peer)
            console.print(peer_label(entity))
            console.print(f"  type: {type(entity).__name__}")
            if isinstance(entity, types.User):
                console.print(
                    f"  username: @{entity.username}" if entity.username else "  username: —"
                )
                console.print(f"  bot: {entity.bot}")
                console.print(
                    f"  bot_can_edit: {getattr(entity, 'bot_can_edit', False)}"
                )

    _run(_resolve())


# ── chat / dialogs ─────────────────────────────────────────────────────────


@chat_app.command("list")
@app.command("dialogs")
def chat_list(
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max dialogs")] = 30,
    unread: Annotated[bool, typer.Option("--unread", help="Only unread")] = False,
) -> None:
    """List recent dialogs (chats)."""

    async def _list() -> None:
        async with authed_client() as client:
            rows = []
            scan = max(limit * 3, limit) if unread else limit
            async for dlg in client.iter_dialogs(limit=scan):
                if unread and not dlg.unread_count:
                    continue
                rows.append((dlg, dlg.entity, dlg.message))
                if len(rows) >= limit:
                    break
            print_dialogs(rows)

    _run(_list())


@app.command("unread")
@msg_app.command("unread")
def msg_unread(
    limit_chats: Annotated[
        int, typer.Option("--chats", "-c", help="Max chats with unread to scan")
    ] = 30,
    per_chat: Annotated[
        int,
        typer.Option(
            "--per-chat",
            "-n",
            help="Max unread messages to show per chat (0 = only list chats)",
        ),
    ] = 20,
    mark_read: Annotated[
        bool,
        typer.Option("--mark-read", help="Mark each shown chat as read after printing"),
    ] = False,
    peer: Annotated[
        Optional[str],
        typer.Option("--peer", "-p", help="Only this chat (if it has unread)"),
    ] = None,
) -> None:
    """Show unread messages (inbox).

    Uses each dialog's read_inbox_max_id so only messages newer than the
    last-read marker are shown (not merely the last N messages).
    """

    async def _unread() -> None:
        async with authed_client() as client:
            # (entity, unread_count, read_inbox_max_id)
            targets: list[tuple[Any, int, int]] = []

            if peer:
                entity = await resolve_peer(client, peer)
                count = 0
                read_max = 0
                async for dlg in client.iter_dialogs(limit=500):
                    if same_entity(dlg.entity, entity):
                        count = dlg.unread_count or 0
                        read_max = getattr(dlg.dialog, "read_inbox_max_id", 0) or 0
                        break
                if count == 0:
                    console.print(f"[dim]No unread in[/] {peer_label(entity)}")
                    return
                targets.append((entity, count, read_max))
            else:
                async for dlg in client.iter_dialogs(limit=300):
                    if not dlg.unread_count:
                        continue
                    read_max = getattr(dlg.dialog, "read_inbox_max_id", 0) or 0
                    targets.append((dlg.entity, dlg.unread_count, read_max))
                    if len(targets) >= limit_chats:
                        break

            if not targets:
                console.print("[dim]No unread messages[/]")
                return

            summary = Table(title="Unread chats")
            summary.add_column("#", style="dim", justify="right")
            summary.add_column("Unread", justify="right", style="yellow")
            summary.add_column("Peer")
            for i, (ent, count, _) in enumerate(targets, 1):
                summary.add_row(str(i), str(count), peer_label(ent))
            console.print(summary)

            if per_chat <= 0:
                return

            for ent, count, read_max in targets:
                n = min(count, per_chat) if count > 0 else per_chat
                # Messages with id > read_inbox_max_id are the unread set
                msgs = await client.get_messages(ent, min_id=read_max, limit=n)
                usable = [m for m in msgs if is_usable_message(m)]
                console.print()
                await print_messages(
                    usable,
                    f"{peer_label(ent)} · {count} unread",
                    client=client,
                )
                if mark_read:
                    await client.send_read_acknowledge(ent)
                    console.print(f"[green]marked read[/] {peer_label(ent)}")

    _run(_unread())


@chat_app.command("info")
def chat_info(
    peer: Annotated[str, typer.Argument(help="Chat / user / @username")],
) -> None:
    """Show details for a chat or user."""

    async def _info() -> None:
        async with authed_client() as client:
            entity = await resolve_peer(client, peer)
            console.print(f"[bold]{peer_label(entity)}[/]")
            console.print(f"  type: {type(entity).__name__}")
            if isinstance(entity, types.User):
                console.print(
                    f"  username: @{entity.username}"
                    if entity.username
                    else "  username: —"
                )
                console.print(f"  bot: {entity.bot}")
                console.print(f"  verified: {entity.verified}")
                console.print(f"  phone: {entity.phone or '—'}")
            else:
                console.print(f"  title: {getattr(entity, 'title', None)}")
                un = getattr(entity, "username", None)
                console.print(f"  username: @{un}" if un else "  username: —")
                console.print(f"  megagroup: {getattr(entity, 'megagroup', False)}")
                console.print(f"  broadcast: {getattr(entity, 'broadcast', False)}")
                # Full channel/chat for participant count
                try:
                    if isinstance(entity, types.Channel):
                        full = await client(
                            functions.channels.GetFullChannelRequest(entity)
                        )
                        console.print(
                            f"  participants: {full.full_chat.participants_count}"
                        )
                        about = getattr(full.full_chat, "about", None)
                        if about:
                            console.print(f"  about: {about}")
                    elif isinstance(entity, types.Chat):
                        full = await client(
                            functions.messages.GetFullChatRequest(entity.id)
                        )
                        participants = getattr(
                            full.full_chat, "participants", None
                        )
                        if participants and getattr(participants, "participants", None):
                            console.print(
                                f"  participants: {len(participants.participants)}"
                            )
                except RPCError as e:
                    console.print(f"  [dim]full info unavailable: {e.__class__.__name__}[/]")

            async for dlg in client.iter_dialogs(limit=500):
                if same_entity(dlg.entity, entity):
                    console.print(f"  unread: {dlg.unread_count}")
                    break

    _run(_info())


@chat_app.command("read")
def chat_read(
    peer: Annotated[str, typer.Argument()],
) -> None:
    """Mark a chat as read."""

    async def _read() -> None:
        async with authed_client() as client:
            entity = await resolve_peer(client, peer)
            await client.send_read_acknowledge(entity)
            console.print(f"[green]Marked read[/] {peer_label(entity)}")

    _run(_read())


@chat_app.command("join")
def chat_join(
    link: Annotated[str, typer.Argument(help="t.me link, @username, or +invite hash")],
) -> None:
    """Join a public channel/group or private invite."""

    async def _join() -> None:
        async with authed_client() as client:
            s = link.strip()
            inv = invite_hash_from_link(s)
            if inv:
                result = await client(
                    functions.messages.ImportChatInviteRequest(inv)
                )
                console.print(f"[green]Joined[/] invite {inv[:8]}…")
                chats = getattr(result, "chats", None) or []
                if chats:
                    console.print(peer_label(chats[0]))
                return

            entity = await resolve_peer(client, s)
            if not isinstance(entity, types.Channel):
                raise SystemExit(
                    f"Not a public channel/supergroup: {peer_label(entity)}. "
                    "For private invites use t.me/+HASH or t.me/joinchat/HASH."
                )
            await client(functions.channels.JoinChannelRequest(entity))
            console.print(f"[green]Joined[/] {peer_label(entity)}")

    _run(_join())


@chat_app.command("leave")
def chat_leave(
    peer: Annotated[str, typer.Argument()],
) -> None:
    """Leave a group or channel (does not delete private chat history)."""

    async def _leave() -> None:
        async with authed_client() as client:
            entity = await resolve_peer(client, peer)
            if isinstance(entity, types.Channel):
                await client(functions.channels.LeaveChannelRequest(entity))
                console.print(f"[green]Left channel/supergroup[/] {peer_label(entity)}")
            elif isinstance(entity, types.Chat):
                me = await client.get_me()
                await client(
                    functions.messages.DeleteChatUserRequest(
                        chat_id=entity.id,
                        user_id=me,
                    )
                )
                console.print(f"[green]Left group[/] {peer_label(entity)}")
            else:
                raise SystemExit(
                    f"{peer_label(entity)} is not a group/channel.\n"
                    "For private chats use:  tg chat delete-dialog <peer>"
                )

    _run(_leave())


@chat_app.command("delete-dialog")
def chat_delete_dialog(
    peer: Annotated[str, typer.Argument()],
    revoke: Annotated[
        bool,
        typer.Option(
            "--revoke/--no-revoke",
            help="Also try to delete history for the other side when possible",
        ),
    ] = False,
) -> None:
    """Delete a dialog (removes chat from your list; for DMs may wipe history)."""

    async def _dd() -> None:
        async with authed_client() as client:
            entity = await resolve_peer(client, peer)
            await client.delete_dialog(entity, revoke=revoke)
            console.print(f"[green]Deleted dialog[/] {peer_label(entity)}")

    _run(_dd())


@chat_app.command("create-group")
def chat_create_group(
    title: Annotated[str, typer.Option("--title", "-t")],
    users: Annotated[
        str, typer.Option("--users", "-u", help="Comma-separated @users or ids")
    ],
    megagroup: Annotated[
        bool,
        typer.Option(
            "--megagroup",
            help="Create a supergroup instead of a legacy basic group (recommended)",
        ),
    ] = True,
) -> None:
    """Create a group. Default is a supergroup (megagroup); use --no-megagroup for basic."""

    async def _cg() -> None:
        async with authed_client() as client:
            peers = [u.strip() for u in users.split(",") if u.strip()]
            if not peers:
                raise typer.BadParameter("Provide at least one user in --users")
            entities = [await resolve_peer(client, p) for p in peers]
            if megagroup:
                result = await client(
                    functions.channels.CreateChannelRequest(
                        title=title,
                        about="",
                        megagroup=True,
                        broadcast=False,
                    )
                )
                chat = result.chats[0]
                for ent in entities:
                    try:
                        await client(
                            functions.channels.InviteToChannelRequest(chat, [ent])
                        )
                    except RPCError as e:
                        console.print(
                            f"[yellow]invite failed[/] {peer_label(ent)}: {e.__class__.__name__}"
                        )
                console.print(f"[green]Created supergroup[/] {peer_label(chat)}")
            else:
                result = await client(
                    functions.messages.CreateChatRequest(users=entities, title=title)
                )
                chats = getattr(result, "chats", None) or []
                chat = chats[0] if chats else None
                console.print(
                    f"[green]Created basic group[/] {peer_label(chat) if chat else title}"
                )

    _run(_cg())


@chat_app.command("create-channel")
def chat_create_channel(
    title: Annotated[str, typer.Option("--title", "-t")],
    about: Annotated[str, typer.Option("--about")] = "",
    megagroup: Annotated[
        bool, typer.Option("--megagroup", help="Create as supergroup instead of channel")
    ] = False,
) -> None:
    """Create a channel (or supergroup with --megagroup)."""

    async def _cc() -> None:
        async with authed_client() as client:
            result = await client(
                functions.channels.CreateChannelRequest(
                    title=title,
                    about=about or "",
                    megagroup=megagroup,
                    broadcast=not megagroup,
                )
            )
            chat = result.chats[0]
            console.print(f"[green]Created[/] {peer_label(chat)}")

    _run(_cc())


@chat_app.command("mute")
def chat_mute(
    peer: Annotated[str, typer.Argument()],
    hours: Annotated[int, typer.Option("--hours", help="0 = forever")] = 0,
) -> None:
    """Mute notifications for a chat."""

    async def _mute() -> None:
        from time import time as now

        async with authed_client() as client:
            entity = await resolve_peer(client, peer)
            mute_until = (2**31 - 1) if hours <= 0 else int(now()) + hours * 3600
            notify_peer = types.InputNotifyPeer(
                peer=await client.get_input_entity(entity)
            )
            await client(
                functions.account.UpdateNotifySettingsRequest(
                    peer=notify_peer,
                    settings=types.InputPeerNotifySettings(mute_until=mute_until),
                )
            )
            console.print(f"[green]Muted[/] {peer_label(entity)} (until={mute_until})")

    _run(_mute())


# ── messages ────────────────────────────────────────────────────────────────


@msg_app.command("send")
@app.command("send")
def msg_send(
    peer: Annotated[str, typer.Argument(help="Recipient @user / chat / id")],
    text: Annotated[Optional[str], typer.Argument(help="Message text")] = None,
    file: Annotated[
        Optional[Path], typer.Option("--file", "-f", help="Attach file/photo")
    ] = None,
    caption: Annotated[Optional[str], typer.Option("--caption", "-c")] = None,
    reply_to: Annotated[
        Optional[int], typer.Option("--reply", "-r", help="Reply to message id")
    ] = None,
    silent: Annotated[bool, typer.Option("--silent")] = False,
    parse: Annotated[
        Optional[str],
        typer.Option("--parse", help="none | md | html (default: none)"),
    ] = "none",
) -> None:
    """Send a text message and/or file."""

    async def _send() -> None:
        body = text if text is not None else (caption or "")
        if not body and not file:
            raise typer.BadParameter("Provide text and/or --file")
        if file is not None and not file.is_file():
            raise typer.BadParameter(f"File not found: {file}")
        parse_mode = parse_mode_arg(parse)
        async with authed_client() as client:
            entity = await resolve_peer(client, peer)
            if file:
                result = await client.send_file(
                    entity,
                    file=str(file),
                    caption=body or None,
                    reply_to=reply_to,
                    silent=silent,
                    parse_mode=parse_mode,
                )
            else:
                result = await client.send_message(
                    entity,
                    body,
                    reply_to=reply_to,
                    silent=silent,
                    parse_mode=parse_mode,
                )
            msg = first_message(result)
            mid = getattr(msg, "id", "?")
            console.print(f"[green]Sent[/] id={mid} → {peer_label(entity)}")

    _run(_send())


@msg_app.command("history")
@app.command("history")
def msg_history(
    peer: Annotated[str, typer.Argument()],
    limit: Annotated[int, typer.Option("--limit", "-n")] = 30,
    search: Annotated[Optional[str], typer.Option("--search", "-s")] = None,
    reverse: Annotated[
        bool, typer.Option("--reverse", help="Oldest first")
    ] = False,
) -> None:
    """Show recent messages in a chat."""

    async def _hist() -> None:
        async with authed_client() as client:
            entity = await resolve_peer(client, peer)
            msgs = await client.get_messages(
                entity, limit=limit, search=search, reverse=reverse
            )
            await print_messages(list(msgs), peer_label(entity), client=client)

    _run(_hist())


@msg_app.command("reply")
def msg_reply(
    peer: Annotated[str, typer.Argument()],
    msg_id: Annotated[int, typer.Argument()],
    text: Annotated[str, typer.Argument()],
) -> None:
    """Reply to a message."""

    async def _reply() -> None:
        async with authed_client() as client:
            entity = await resolve_peer(client, peer)
            result = await client.send_message(entity, text, reply_to=msg_id)
            msg = first_message(result)
            console.print(f"[green]Replied[/] id={getattr(msg, 'id', '?')}")

    _run(_reply())


@msg_app.command("forward")
def msg_forward(
    src: Annotated[str, typer.Argument(help="Source chat")],
    dest: Annotated[str, typer.Argument(help="Destination chat")],
    ids: Annotated[str, typer.Argument(help="Message ids, comma-separated")],
) -> None:
    """Forward messages between chats."""

    async def _fwd() -> None:
        async with authed_client() as client:
            s = await resolve_peer(client, src)
            d = await resolve_peer(client, dest)
            result = await client.forward_messages(d, parse_msg_ids(ids), s)
            n = len(result) if isinstance(result, list) else 1
            console.print(f"[green]Forwarded[/] {n} message(s)")

    _run(_fwd())


@msg_app.command("edit")
def msg_edit(
    peer: Annotated[str, typer.Argument()],
    msg_id: Annotated[int, typer.Argument()],
    text: Annotated[str, typer.Argument()],
) -> None:
    """Edit one of your messages."""

    async def _edit() -> None:
        async with authed_client() as client:
            entity = await resolve_peer(client, peer)
            await client.edit_message(entity, msg_id, text)
            console.print(f"[green]Edited[/] {msg_id}")

    _run(_edit())


@msg_app.command("delete")
def msg_delete(
    peer: Annotated[str, typer.Argument()],
    ids: Annotated[str, typer.Argument(help="Message ids, comma-separated")],
    revoke: Annotated[
        bool,
        typer.Option("--revoke/--no-revoke", help="Delete for everyone when possible"),
    ] = True,
) -> None:
    """Delete messages."""

    async def _del() -> None:
        async with authed_client() as client:
            entity = await resolve_peer(client, peer)
            mid = parse_msg_ids(ids)
            await client.delete_messages(entity, mid, revoke=revoke)
            console.print(f"[green]Deleted[/] {','.join(map(str, mid))}")

    _run(_del())


@msg_app.command("search")
@app.command("search")
def msg_search(
    query: Annotated[str, typer.Argument()],
    peer: Annotated[
        Optional[str], typer.Option("--peer", "-p", help="Limit to one chat")
    ] = None,
    limit: Annotated[int, typer.Option("--limit", "-n")] = 20,
) -> None:
    """Global or per-chat message search."""

    async def _search() -> None:
        async with authed_client() as client:
            if peer:
                entity = await resolve_peer(client, peer)
                msgs = await client.get_messages(entity, limit=limit, search=query)
                await print_messages(list(msgs), peer_label(entity), client=client)
                return

            results = await client(
                functions.messages.SearchGlobalRequest(
                    q=query,
                    filter=types.InputMessagesFilterEmpty(),
                    min_date=None,
                    max_date=None,
                    offset_rate=0,
                    offset_peer=types.InputPeerEmpty(),
                    offset_id=0,
                    limit=limit,
                )
            )
            table = Table(title=f"Search: {query}")
            table.add_column("ID")
            table.add_column("Date")
            table.add_column("Peer")
            table.add_column("Text")
            from telegram_cli.format import fmt_dt, msg_preview

            # Index chats/users from result for labels
            entities: dict[int, Any] = {}
            for u in getattr(results, "users", []) or []:
                entities[u.id] = u
            for c in getattr(results, "chats", []) or []:
                entities[c.id] = c

            for m in results.messages:
                if not isinstance(m, types.Message):
                    continue
                peer_obj = getattr(m, "peer_id", None)
                label = str(peer_obj)
                try:
                    # resolve from bundled entities when possible
                    if isinstance(peer_obj, types.PeerUser) and peer_obj.user_id in entities:
                        label = peer_label(entities[peer_obj.user_id])
                    elif isinstance(peer_obj, types.PeerChannel) and peer_obj.channel_id in entities:
                        label = peer_label(entities[peer_obj.channel_id])
                    elif isinstance(peer_obj, types.PeerChat) and peer_obj.chat_id in entities:
                        label = peer_label(entities[peer_obj.chat_id])
                except Exception:
                    pass
                table.add_row(str(m.id), fmt_dt(m.date), label, msg_preview(m, 80))
            console.print(table)

    _run(_search())


@msg_app.command("pin")
def msg_pin(
    peer: Annotated[str, typer.Argument()],
    msg_id: Annotated[int, typer.Argument()],
    silent: Annotated[bool, typer.Option("--silent")] = True,
) -> None:
    """Pin a message."""

    async def _pin() -> None:
        async with authed_client() as client:
            entity = await resolve_peer(client, peer)
            await client.pin_message(entity, msg_id, notify=not silent)
            console.print(f"[green]Pinned[/] {msg_id}")

    _run(_pin())


@msg_app.command("react")
def msg_react(
    peer: Annotated[str, typer.Argument()],
    msg_id: Annotated[int, typer.Argument()],
    emoji: Annotated[str, typer.Argument(help="Emoji reaction, e.g. 👍")] = "👍",
) -> None:
    """Add an emoji reaction to a message."""

    async def _react() -> None:
        async with authed_client() as client:
            entity = await resolve_peer(client, peer)
            try:
                await client(
                    functions.messages.SendReactionRequest(
                        peer=entity,
                        msg_id=msg_id,
                        reaction=[types.ReactionEmoji(emoticon=emoji)],
                    )
                )
            except RPCError as e:
                name = e.__class__.__name__
                if "Premium" in name:
                    raise SystemExit(
                        "Reactions failed: Telegram Premium required on this account "
                        f"({name})."
                    ) from e
                raise SystemExit(f"Reaction failed: {name}: {e}") from e
            console.print(f"[green]Reacted[/] {emoji} on {msg_id}")

    _run(_react())


@msg_app.command("get")
def msg_get(
    peer: Annotated[str, typer.Argument()],
    msg_id: Annotated[int, typer.Argument()],
    json_out: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Get a single message by id."""

    async def _get() -> None:
        async with authed_client() as client:
            entity = await resolve_peer(client, peer)
            msgs = await client.get_messages(entity, ids=msg_id)
            m: Message | None
            if isinstance(msgs, list):
                m = msgs[0] if msgs else None
            else:
                m = msgs
            if not is_usable_message(m):
                console.print("[red]Message not found[/]")
                raise typer.Exit(1)
            assert m is not None
            if json_out:
                console.print_json(
                    json.dumps(
                        {
                            "id": m.id,
                            "date": m.date.isoformat() if m.date else None,
                            "text": m.message,
                            "out": m.out,
                            "media": type(m.media).__name__ if m.media else None,
                        }
                    )
                )
            else:
                await print_messages([m], peer_label(entity), client=client)
                if m.message:
                    console.print(m.message)

    _run(_get())


@msg_app.command("listen")
@app.command("listen")
def msg_listen(
    peer: Annotated[
        Optional[str],
        typer.Option("--peer", "-p", help="Only this chat (optional)"),
    ] = None,
) -> None:
    """Stream new messages until Ctrl+C."""

    async def _listen() -> None:
        from telethon import events

        async with authed_client() as client:
            entity = await resolve_peer(client, peer) if peer else None
            console.print("[dim]Listening… Ctrl+C to stop[/]")

            @client.on(events.NewMessage(chats=entity))
            async def handler(event: events.NewMessage.Event) -> None:
                chat = await event.get_chat()
                sender = await event.get_sender()
                console.print(
                    f"[cyan]{event.id}[/] "
                    f"[bold]{get_display_name(chat)}[/] "
                    f"← {get_display_name(sender) if sender else '?'}: "
                    f"{(event.message.message or '[media]')[:200]}"
                )

            try:
                await client.run_until_disconnected()
            except asyncio.CancelledError:
                pass

    try:
        _run(_listen())
    except KeyboardInterrupt:
        console.print("\n[dim]stopped[/]")


# ── media ───────────────────────────────────────────────────────────────────


@media_app.command("upload")
def media_upload(
    peer: Annotated[str, typer.Argument()],
    path: Annotated[Path, typer.Argument(help="Local file path")],
    caption: Annotated[Optional[str], typer.Option("--caption", "-c")] = None,
    force_document: Annotated[
        bool, typer.Option("--document", help="Send as document, not photo/video")
    ] = False,
    voice: Annotated[bool, typer.Option("--voice", help="Send audio as voice note")] = False,
) -> None:
    """Upload and send a file to a chat."""

    async def _up() -> None:
        if not path.is_file():
            raise typer.BadParameter(f"File not found: {path}")
        async with authed_client() as client:
            entity = await resolve_peer(client, peer)
            result = await client.send_file(
                entity,
                file=str(path),
                caption=caption,
                force_document=force_document,
                voice_note=voice,
            )
            msg = first_message(result)
            console.print(
                f"[green]Uploaded[/] msg_id={getattr(msg, 'id', '?')} → {peer_label(entity)}"
            )

    _run(_up())


@media_app.command("download")
def media_download(
    peer: Annotated[str, typer.Argument()],
    msg_id: Annotated[int, typer.Argument()],
    out: Annotated[
        Optional[Path],
        typer.Option("--out", "-o", help="Output file or directory"),
    ] = None,
) -> None:
    """Download media from a message."""

    async def _dl() -> None:
        async with authed_client() as client:
            entity = await resolve_peer(client, peer)
            msg = await client.get_messages(entity, ids=msg_id)
            if isinstance(msg, list):
                msg = msg[0] if msg else None
            if not is_usable_message(msg) or not getattr(msg, "media", None):
                console.print("[red]No media on that message[/]")
                raise typer.Exit(1)
            DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
            dest = out or DOWNLOAD_DIR
            path = await client.download_media(msg, file=str(dest))
            console.print(f"[green]Downloaded[/] {path}")

    _run(_dl())


@media_app.command("download-chat")
def media_download_chat(
    peer: Annotated[str, typer.Argument()],
    limit: Annotated[int, typer.Option("--limit", "-n")] = 20,
    out: Annotated[Optional[Path], typer.Option("--out", "-o")] = None,
) -> None:
    """Download recent media from a chat."""

    async def _dlc() -> None:
        async with authed_client() as client:
            entity = await resolve_peer(client, peer)
            dest = out or (
                DOWNLOAD_DIR / str(getattr(entity, "username", None) or entity.id)
            )
            dest.mkdir(parents=True, exist_ok=True)
            n = 0
            async for msg in client.iter_messages(entity, limit=limit):
                if not msg.media:
                    continue
                path = await client.download_media(msg, file=str(dest))
                if path:
                    console.print(f"  {msg.id} → {path}")
                    n += 1
            console.print(f"[green]Downloaded {n} file(s)[/] → {dest}")

    _run(_dlc())


# ── contacts ────────────────────────────────────────────────────────────────


@contacts_app.command("list")
def contacts_list(
    limit: Annotated[int, typer.Option("--limit", "-n")] = 100,
) -> None:
    """List contacts."""

    async def _cl() -> None:
        async with authed_client() as client:
            result = await client(functions.contacts.GetContactsRequest(hash=0))
            users = getattr(result, "users", []) or []
            table = Table(title="Contacts")
            table.add_column("ID")
            table.add_column("Name")
            table.add_column("Username")
            table.add_column("Phone")
            for u in users[:limit]:
                if not isinstance(u, types.User):
                    continue
                table.add_row(
                    str(u.id),
                    get_display_name(u),
                    f"@{u.username}" if u.username else "",
                    u.phone or "",
                )
            console.print(table)

    _run(_cl())


@contacts_app.command("search")
def contacts_search(
    query: Annotated[str, typer.Argument()],
    limit: Annotated[int, typer.Option("--limit", "-n")] = 20,
) -> None:
    """Search contacts / global users."""

    async def _cs() -> None:
        async with authed_client() as client:
            result = await client(
                functions.contacts.SearchRequest(q=query, limit=limit)
            )
            table = Table(title=f"Search users: {query}")
            table.add_column("ID")
            table.add_column("Name")
            table.add_column("Username")
            for u in result.users:
                if isinstance(u, types.User):
                    table.add_row(
                        str(u.id),
                        get_display_name(u),
                        f"@{u.username}" if u.username else "",
                    )
            console.print(table)

    _run(_cs())


@contacts_app.command("block")
def contacts_block(
    peer: Annotated[str, typer.Argument()],
    unblock: Annotated[bool, typer.Option("--unblock")] = False,
) -> None:
    """Block or unblock a user."""

    async def _block() -> None:
        async with authed_client() as client:
            entity = await resolve_peer(client, peer)
            if unblock:
                await client(functions.contacts.UnblockRequest(id=entity))
                console.print(f"[green]Unblocked[/] {peer_label(entity)}")
            else:
                await client(functions.contacts.BlockRequest(id=entity))
                console.print(f"[green]Blocked[/] {peer_label(entity)}")

    _run(_block())


@contacts_app.command("add")
def contacts_add(
    phone: Annotated[str, typer.Option("--phone", "-p")],
    first_name: Annotated[str, typer.Option("--name", "-n")],
    last_name: Annotated[str, typer.Option("--last")] = "",
) -> None:
    """Add a contact by phone number."""

    async def _add() -> None:
        import random

        async with authed_client() as client:
            result = await client(
                functions.contacts.ImportContactsRequest(
                    contacts=[
                        types.InputPhoneContact(
                            client_id=random.randint(1, 2**31 - 1),
                            phone=phone,
                            first_name=first_name,
                            last_name=last_name or "",
                        )
                    ]
                )
            )
            console.print(f"[green]Imported[/] {len(result.users)} user(s)")
            for u in result.users:
                console.print(f"  {peer_label(u)}")

    _run(_add())


# ── profile ─────────────────────────────────────────────────────────────────


@profile_app.command("get")
def profile_get() -> None:
    """Show your profile (alias of whoami)."""
    whoami()


@profile_app.command("set-name")
def profile_set_name(
    first: Annotated[str, typer.Argument()],
    last: Annotated[str, typer.Argument()] = "",
) -> None:
    """Update your first/last name."""

    async def _sn() -> None:
        async with authed_client() as client:
            await client(
                functions.account.UpdateProfileRequest(
                    first_name=first, last_name=last
                )
            )
            console.print(f"[green]Name set[/] {first} {last}".rstrip())

    _run(_sn())


@profile_app.command("set-about")
def profile_set_about(
    about: Annotated[str, typer.Argument()],
) -> None:
    """Update your bio/about."""

    async def _sa() -> None:
        async with authed_client() as client:
            await client(functions.account.UpdateProfileRequest(about=about[:70]))
            console.print("[green]About updated[/]")

    _run(_sa())


@profile_app.command("set-photo")
def profile_set_photo(
    path: Annotated[Path, typer.Argument()],
) -> None:
    """Update your profile photo."""

    async def _sp() -> None:
        if not path.is_file():
            raise typer.BadParameter(f"File not found: {path}")
        async with authed_client() as client:
            file = await client.upload_file(str(path))
            await client(functions.photos.UploadProfilePhotoRequest(file=file))
            console.print(f"[green]Profile photo set[/] from {path}")

    _run(_sp())


# ── bots ────────────────────────────────────────────────────────────────────


@bots_app.command("create")
def bots_create(
    name: Annotated[str, typer.Option("--name", "-n", help="Display name")],
    username: Annotated[str, typer.Option("--username", "-u", help="Desired @handle")],
    photo: Annotated[
        Optional[Path], typer.Option("--photo", "-p", help="Profile photo path")
    ] = None,
    about: Annotated[Optional[str], typer.Option("--about")] = None,
    description: Annotated[Optional[str], typer.Option("--description", "-d")] = None,
) -> None:
    """Create a bot via @BotFather; optionally set photo/about/description."""

    async def _create() -> None:
        if photo is not None and not photo.is_file():
            raise typer.BadParameter(f"Photo not found: {photo}")
        async with authed_client() as client:
            info = await create_via_botfather(client, name, username)
            console.print(
                f"[green]Created[/] {info['username_at']}  "
                f"token={info['token'][:16]}…"
            )
            bot = await resolve_bot(client, info["username"])
            photo_set = False
            if photo:
                await set_bot_photo(client, bot, photo)
                photo_set = True
                console.print(f"[green]Photo set[/] from {photo}")
            if about is not None or description is not None:
                await set_bot_info(
                    client,
                    bot,
                    name=name,
                    about=about,
                    description=description,
                )
                console.print("[green]Info set[/]")
            elif name:
                # Always sync display name from create args
                await set_bot_info(client, bot, name=name)
            info["photo_set"] = photo_set
            path = save_bot_credentials(info, str(photo) if photo else None)
            console.print(f"credentials → {path}")
            console.print(f"token: [bold]{info['token']}[/]")
            console.print(f"link:  https://t.me/{info['username']}")

    _run(_create())


@bots_app.command("set-photo")
def bots_set_photo(
    bot: Annotated[str, typer.Argument(help="@bot or username")],
    photo: Annotated[Path, typer.Argument()],
) -> None:
    """Set a bot profile photo (owner MTProto)."""

    async def _sp() -> None:
        if not photo.is_file():
            raise typer.BadParameter(f"Photo not found: {photo}")
        async with authed_client() as client:
            entity = await resolve_bot(client, bot)
            result = await set_bot_photo(client, entity, photo)
            console.print(
                f"[green]Photo set[/] on @{entity.username} "
                f"(photo_id={getattr(getattr(result, 'photo', None), 'id', result)})"
            )
            cred = BOTS_DIR / f"{entity.username}.json"
            if cred.is_file():
                data = json.loads(cred.read_text())
                data["photo_set"] = True
                data["photo"] = str(photo)
                cred.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    _run(_sp())


@bots_app.command("set-info")
def bots_set_info(
    bot: Annotated[str, typer.Argument()],
    name: Annotated[Optional[str], typer.Option("--name")] = None,
    about: Annotated[Optional[str], typer.Option("--about")] = None,
    description: Annotated[Optional[str], typer.Option("--description", "-d")] = None,
) -> None:
    """Set bot name / about / description."""

    async def _si() -> None:
        if name is None and about is None and description is None:
            raise typer.BadParameter("Provide at least one of --name / --about / --description")
        async with authed_client() as client:
            entity = await resolve_bot(client, bot)
            await set_bot_info(
                client, entity, name=name, about=about, description=description
            )
            console.print(f"[green]Updated[/] @{entity.username}")

    _run(_si())


@bots_app.command("list")
def bots_list() -> None:
    """List bots you own (admined + dialogs) and saved credentials."""

    async def _list() -> None:
        async with authed_client() as client:
            by_id: dict[int, types.User] = {}

            if hasattr(functions.bots, "GetAdminedBotsRequest"):
                try:
                    res = await client(functions.bots.GetAdminedBotsRequest())
                    users = getattr(res, "users", None) or (
                        res if isinstance(res, list) else []
                    )
                    for u in users:
                        if isinstance(u, types.User):
                            by_id[u.id] = u
                except Exception as e:
                    console.print(f"[dim]GetAdminedBots: {type(e).__name__}: {e}[/]")

            async for dlg in client.iter_dialogs(limit=500):
                ent = dlg.entity
                if (
                    isinstance(ent, types.User)
                    and ent.bot
                    and getattr(ent, "bot_can_edit", False)
                ):
                    by_id[ent.id] = ent

            table = Table(title="Your bots")
            table.add_column("Username")
            table.add_column("ID")
            table.add_column("Name")
            for u in sorted(by_id.values(), key=lambda x: (x.username or "").lower()):
                table.add_row(
                    f"@{u.username}" if u.username else "—",
                    str(u.id),
                    get_display_name(u),
                )
            console.print(table)

        if BOTS_DIR.is_dir():
            files = sorted(BOTS_DIR.glob("*.json"))
            if files:
                console.print("\n[bold]Saved credentials[/]")
                for f in files:
                    data = json.loads(f.read_text())
                    console.print(
                        f"  {data.get('username_at') or data.get('username')}  "
                        f"token={str(data.get('token', ''))[:12]}…  "
                        f"photo={data.get('photo_set')}"
                    )

    _run(_list())


@bots_app.command("token")
def bots_token(
    bot: Annotated[str, typer.Argument(help="@bot username")],
) -> None:
    """Show saved bot token from bots/ directory."""
    uname = bot.lstrip("@")
    path = BOTS_DIR / f"{uname}.json"
    if not path.is_file():
        console.print(f"[red]No saved credentials[/] at {path}")
        console.print("Create with: tg bots create …  or place JSON in bots/")
        raise typer.Exit(1)
    data = json.loads(path.read_text())
    console.print(data.get("token", ""))


@bots_app.command("father")
def bots_father(
    text: Annotated[str, typer.Argument(help="Raw message to @BotFather")],
) -> None:
    """Send a raw command/message to @BotFather and print the reply."""

    async def _bf() -> None:
        async with authed_client() as client:
            reply = await botfather_send(client, text)
            console.print(reply)

    _run(_bf())


@bots_app.command("create-batch")
def bots_create_batch(
    csv_path: Annotated[
        Path,
        typer.Argument(
            help="CSV with botfather_newbot_name, botfather_username, botpic_path…"
        ),
    ],
    only: Annotated[
        Optional[int],
        typer.Option("--only", help="1-based row number to process (single agent)"),
    ] = None,
    skip_photo: Annotated[bool, typer.Option("--skip-photo")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
) -> None:
    """Create bots from a CSV (columns: botfather_newbot_name, botfather_username, …)."""
    import csv

    async def _batch() -> None:
        if not csv_path.is_file():
            raise typer.BadParameter(f"CSV not found: {csv_path}")
        rows = list(csv.DictReader(csv_path.open(encoding="utf-8")))
        if only is not None:
            rows = [r for r in rows if int(r.get("order") or 0) == only]
            if not rows:
                raise SystemExit(f"No CSV row with order={only}")
        async with authed_client() as client:
            for row in rows:
                name = row.get("botfather_newbot_name") or row.get("persona_name")
                username = row.get("botfather_username") or ""
                photo_raw = row.get("botpic_path") or ""
                about = row.get("botfather_about_text") or None
                description = row.get("botfather_description") or None
                console.print(f"\n[bold]#{row.get('order')} {name} @{username}[/]")
                if dry_run:
                    console.print("  [dim]dry-run skip[/]")
                    continue
                photo: Path | None = None
                if photo_raw and not skip_photo:
                    p = Path(photo_raw)
                    if not p.is_file():
                        # Resolve relative paths and common local layouts
                        slug = row.get("bundle_slug") or ""
                        candidates = [
                            Path(photo_raw),
                            Path.cwd() / photo_raw,
                        ]
                        if slug:
                            candidates.extend(
                                [
                                    Path(slug) / "profile_photo" / "selected.jpg",
                                    Path("profile_photo") / "selected.jpg",
                                ]
                            )
                        # If CSV has an absolute path, also try basename under cwd
                        if p.name:
                            candidates.append(Path.cwd() / p.name)
                            candidates.append(
                                Path.cwd() / "profile_photo" / p.name
                            )
                        for cand in candidates:
                            if cand.is_file():
                                p = cand
                                break
                    photo = p if p.is_file() else None
                    if photo is None:
                        console.print(f"  [yellow]photo missing:[/] {photo_raw}")

                info = await create_via_botfather(client, name, username)
                bot = await resolve_bot(client, info["username"])
                if photo:
                    try:
                        await set_bot_photo(client, bot, photo)
                        info["photo_set"] = True
                        console.print(f"  [green]photo OK[/] {photo}")
                    except Exception as e:
                        info["photo_set"] = False
                        console.print(f"  [red]photo fail:[/] {e}")
                else:
                    info["photo_set"] = False
                if about or description:
                    await set_bot_info(
                        client, bot, name=name, about=about, description=description
                    )
                path = save_bot_credentials(info, str(photo) if photo else None)
                console.print(f"  token: {info['token']}")
                console.print(f"  saved: {path}")

    _run(_batch())


# ── raw / advanced ──────────────────────────────────────────────────────────


def _resolve_tl_request(method: str) -> Any:
    """Resolve dotted TL name to a Request class, e.g. help.GetConfig."""
    parts = method.strip().split(".")
    if not parts:
        raise SystemExit("Empty method name")
    obj: Any = functions
    for i, p in enumerate(parts):
        candidates = [p]
        if not p.endswith("Request"):
            # GetConfig → GetConfigRequest; getConfig → GetConfigRequest
            camel = p[0].upper() + p[1:] if p else p
            candidates.append(camel)
            candidates.append(camel + "Request")
            candidates.append(p + "Request")
        found = None
        for name in candidates:
            if hasattr(obj, name):
                found = getattr(obj, name)
                break
        if found is None:
            # module names are lowercase: messages, help, …
            if hasattr(obj, p.lower()):
                found = getattr(obj, p.lower())
            elif hasattr(obj, p):
                found = getattr(obj, p)
        if found is None:
            available = [x for x in dir(obj) if not x.startswith("_")][:30]
            raise SystemExit(
                f"Unknown TL path segment {p!r} in {method!r}. "
                f"Examples under current node: {available}"
            )
        obj = found
    return obj


@app.command("raw")
def raw_cmd(
    method: Annotated[str, typer.Argument(help="e.g. help.GetConfig")],
    params: Annotated[
        Optional[str],
        typer.Option("--params", "-p", help="JSON object of kwargs"),
    ] = None,
) -> None:
    """Call a raw TL method (advanced). Example: tg raw help.GetConfig"""

    async def _raw() -> None:
        async with authed_client() as client:
            cls = _resolve_tl_request(method)
            if not callable(cls):
                raise SystemExit(f"Not a callable TL request: {cls}")
            kwargs = json.loads(params) if params else {}
            try:
                req = cls(**kwargs) if kwargs else cls()
            except TypeError as e:
                raise SystemExit(f"Bad params for {method}: {e}") from e
            result = await client(req)
            console.print(result)

    _run(_raw())


if __name__ == "__main__":
    app()
