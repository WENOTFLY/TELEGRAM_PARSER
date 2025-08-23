from __future__ import annotations

"""Utilities for polling Telegram accounts and persisting messages.

This module focuses on reading new messages from channels that users have
subscribed to.  For each active ``TGAccount`` we create a Telethon client using
its stored session, iterate over the channels it is subscribed to and persist
any new messages.  Media files are uploaded to Supabase/S3 and referenced from
``media_assets``.

The function :func:`poll_accounts` is intentionally side‑effect free with
respect to scheduling – callers may run it in a loop or trigger it manually.
"""

from typing import Any
import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from config import settings
from web.models import (
    AccountChannelState,
    MediaAsset,
    Message,
    TGAccount,
)

logger = logging.getLogger(__name__)


async def poll_accounts(session: Session, supabase: Any) -> None:
    """Poll Telegram accounts and store new messages.

    Parameters
    ----------
    session:
        SQLAlchemy session connected to the application's database.
    supabase:
        Client instance used for uploading media files.  The client is expected
        to provide ``storage.from_(bucket).upload(...)`` and
        ``get_public_url`` methods similar to the official supabase-py client.
    """

    try:  # Import Telethon lazily so tests not requiring it do not fail.
        from telethon import TelegramClient, errors
        from telethon.sessions import StringSession
    except Exception as exc:  # pragma: no cover - Telethon is required at run time
        raise RuntimeError("Telethon library is required to run the worker") from exc

    accounts = session.scalars(
        select(TGAccount).where(TGAccount.is_active.is_(True))
    ).all()

    for account in accounts:
        if not account.session_cipher:
            continue

        client = TelegramClient(
            StringSession(account.session_cipher),
            settings.telegram_api_id,
            settings.telegram_api_hash,
        )
        await client.connect()
        try:
            for state in account.states:
                await _fetch_channel_messages(client, state, session, supabase, errors)
        finally:
            await client.disconnect()


async def _fetch_channel_messages(
    client: "TelegramClient",
    state: AccountChannelState,
    session: Session,
    supabase: Any,
    errors: Any,
) -> None:
    """Fetch and persist new messages for a single channel."""

    last_id = state.last_msg_id or 0
    attempt = 0
    while True:
        try:
            async for msg in client.iter_messages(
                state.channel.username, min_id=last_id, reverse=True
            ):
                await _store_message(msg, state, session, supabase)
                last_id = msg.id
            state.last_msg_id = last_id
            session.commit()
            break
        except errors.FloodWaitError as e:
            wait_time = e.seconds * (2**attempt)
            logger.warning(
                "FLOOD_WAIT for %s seconds, retrying in %s", e.seconds, wait_time
            )
            await asyncio.sleep(wait_time)
            attempt += 1


async def _store_message(
    msg: Any, state: AccountChannelState, session: Session, supabase: Any
) -> None:
    """Normalize and persist a single Telegram message."""

    db_message = Message(
        channel_id=state.channel_id,
        msg_id=msg.id,
        date=getattr(msg, "date", None),
        text=getattr(msg, "text", None),
        author=str(getattr(msg, "sender_id", None)) if getattr(msg, "sender_id", None) else None,
        views=getattr(msg, "views", None),
        reactions=None,
        forwards=getattr(msg, "forwards", None),
        comments=getattr(msg, "replies", None),
        lang=None,
        type="media" if msg.media else "text",
        hashtags=[],
        links=[],
        media_present=bool(msg.media),
    )
    session.add(db_message)
    session.flush()  # obtain ``id`` for potential media assets

    if msg.media:
        media_bytes = await msg.download_media(bytes)
        path = f"{state.channel_id}/{msg.id}"
        bucket = supabase.storage.from_(settings.supabase_bucket)
        bucket.upload(path, media_bytes)
        url = bucket.get_public_url(path)
        media = MediaAsset(
            message_id=db_message.id,
            kind=msg.media.__class__.__name__,
            url=url,
            size=len(media_bytes) if media_bytes else None,
            format=None,
            hash=None,
        )
        session.add(media)
    session.commit()
