from __future__ import annotations

"""Database models for the application."""

from datetime import datetime
from enum import Enum

import sqlalchemy as sa
from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""


class Visibility(str, Enum):
    PUBLIC = "public"
    PRIVATE = "private"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(255))
    first_name: Mapped[str | None] = mapped_column(String(255))
    last_name: Mapped[str | None] = mapped_column(String(255))
    photo_url: Mapped[str | None] = mapped_column(String)
    role: Mapped[str | None] = mapped_column(String(50))
    plan: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    tg_accounts: Mapped[list["TGAccount"]] = relationship(back_populates="user")
    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="user")
    editor_results: Mapped[list["EditorResult"]] = relationship(back_populates="user")
    content_packages: Mapped[list["ContentPackage"]] = relationship(back_populates="user")
    ai_usage: Mapped[list["AIUsage"]] = relationship(back_populates="user")


class TGAccount(Base):
    __tablename__ = "tg_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    session_cipher: Mapped[str] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(String(32))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    kver: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="tg_accounts")
    channels: Mapped[list["Channel"]] = relationship(back_populates="owner_account")
    states: Mapped[list["AccountChannelState"]] = relationship(back_populates="account")


class Channel(Base):
    __tablename__ = "channels"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str | None] = mapped_column(String(255), unique=True)
    title: Mapped[str | None] = mapped_column(String(255))
    visibility: Mapped[Visibility] = mapped_column(SAEnum(Visibility), default=Visibility.PUBLIC)
    owner_account_id: Mapped[int | None] = mapped_column(ForeignKey("tg_accounts.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_parsed_at: Mapped[datetime | None] = mapped_column(DateTime)

    owner_account: Mapped[TGAccount | None] = relationship(back_populates="channels")
    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="channel")
    messages: Mapped[list["Message"]] = relationship(back_populates="channel")
    states: Mapped[list["AccountChannelState"]] = relationship(back_populates="channel")


class Subscription(Base):
    __tablename__ = "subscriptions"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    channel_id: Mapped[int] = mapped_column(
        ForeignKey("channels.id", ondelete="CASCADE"), primary_key=True
    )
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="subscriptions")
    channel: Mapped["Channel"] = relationship(back_populates="subscriptions")


class AccountChannelState(Base):
    __tablename__ = "account_channel_state"

    account_id: Mapped[int] = mapped_column(
        ForeignKey("tg_accounts.id", ondelete="CASCADE"), primary_key=True
    )
    channel_id: Mapped[int] = mapped_column(
        ForeignKey("channels.id", ondelete="CASCADE"), primary_key=True
    )
    last_msg_id: Mapped[int | None] = mapped_column(Integer)

    account: Mapped["TGAccount"] = relationship(back_populates="states")
    channel: Mapped["Channel"] = relationship(back_populates="states")


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        sa.UniqueConstraint("channel_id", "msg_id", name="uq_messages_channel_msg"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    channel_id: Mapped[int] = mapped_column(
        ForeignKey("channels.id", ondelete="CASCADE"), nullable=False
    )
    msg_id: Mapped[int] = mapped_column(Integer, nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    text: Mapped[str | None] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(String(255))
    views: Mapped[int | None] = mapped_column(Integer)
    reactions: Mapped[int | None] = mapped_column(Integer)
    forwards: Mapped[int | None] = mapped_column(Integer)
    comments: Mapped[int | None] = mapped_column(Integer)
    lang: Mapped[str | None] = mapped_column(String(16))
    type: Mapped[str | None] = mapped_column(String(50))
    hashtags: Mapped[list[str] | None] = mapped_column(ARRAY(String), default=list)
    links: Mapped[list[str] | None] = mapped_column(ARRAY(String), default=list)
    media_present: Mapped[bool] = mapped_column(Boolean, default=False)

    channel: Mapped["Channel"] = relationship(back_populates="messages")
    media_assets: Mapped[list["MediaAsset"]] = relationship(back_populates="message")
    topic_messages: Mapped[list["TopicMessage"]] = relationship(back_populates="message")


class MediaAsset(Base):
    __tablename__ = "media_assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[int] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(50))
    url: Mapped[str] = mapped_column(String)
    size: Mapped[int | None] = mapped_column(Integer)
    format: Mapped[str | None] = mapped_column(String(50))
    hash: Mapped[str | None] = mapped_column(String(128))

    message: Mapped["Message"] = relationship(back_populates="media_assets")


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    messages: Mapped[list["TopicMessage"]] = relationship(back_populates="topic")
    editor_results: Mapped[list["EditorResult"]] = relationship(back_populates="topic")


class TopicMessage(Base):
    __tablename__ = "topic_messages"

    topic_id: Mapped[int] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True
    )
    message_id: Mapped[int] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), primary_key=True
    )

    topic: Mapped["Topic"] = relationship(back_populates="messages")
    message: Mapped["Message"] = relationship(back_populates="topic_messages")


class Ranking(Base):
    __tablename__ = "ranking"
    __table_args__ = (
        sa.PrimaryKeyConstraint("entity_kind", "entity_id", "window"),
    )

    entity_kind: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[int] = mapped_column(Integer)
    window: Mapped[str] = mapped_column(String(10))
    score: Mapped[float] = mapped_column(Float)
    indexed: Mapped[datetime | None] = mapped_column(DateTime)


class EditorResult(Base):
    __tablename__ = "editor_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    topic_id: Mapped[int | None] = mapped_column(ForeignKey("topics.id"))
    message_ids: Mapped[list[int] | None] = mapped_column(ARRAY(Integer))
    language: Mapped[str | None] = mapped_column(String(16))
    headline: Mapped[str | None] = mapped_column(Text)
    dek: Mapped[str | None] = mapped_column(Text)
    body_variants: Mapped[dict | None] = mapped_column(JSONB)
    key_points: Mapped[dict | None] = mapped_column(JSONB)
    source_links: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="editor_results")
    topic: Mapped[Topic | None] = relationship(back_populates="editor_results")
    image_briefs: Mapped[list["ImageBrief"]] = relationship(back_populates="editor_result")
    content_packages: Mapped[list["ContentPackage"]] = relationship(back_populates="editor_result")


class ImageBrief(Base):
    __tablename__ = "image_briefs"

    id: Mapped[int] = mapped_column(primary_key=True)
    editor_result_id: Mapped[int] = mapped_column(
        ForeignKey("editor_results.id", ondelete="CASCADE")
    )
    title: Mapped[str | None] = mapped_column(String(255))
    prompt: Mapped[str | None] = mapped_column(Text)
    negative: Mapped[str | None] = mapped_column(Text)
    size: Mapped[str | None] = mapped_column(String(50))
    variants: Mapped[int | None] = mapped_column(Integer)
    caption: Mapped[str | None] = mapped_column(Text)
    style_tags: Mapped[list[str] | None] = mapped_column(ARRAY(String))

    editor_result: Mapped["EditorResult"] = relationship(back_populates="image_briefs")


class ContentPackage(Base):
    __tablename__ = "content_packages"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    editor_result_id: Mapped[int] = mapped_column(
        ForeignKey("editor_results.id", ondelete="CASCADE")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="content_packages")
    editor_result: Mapped["EditorResult"] = relationship(back_populates="content_packages")
    items: Mapped[list["ContentPackageItem"]] = relationship(back_populates="package")


class ContentPackageItem(Base):
    __tablename__ = "content_package_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    package_id: Mapped[int] = mapped_column(
        ForeignKey("content_packages.id", ondelete="CASCADE")
    )
    platform: Mapped[str | None] = mapped_column(String(50))
    post_time: Mapped[datetime | None] = mapped_column(DateTime)
    post_text: Mapped[dict | None] = mapped_column(JSONB)
    hashtags: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    cta: Mapped[str | None] = mapped_column(String(255))
    image_url: Mapped[str | None] = mapped_column(String)

    package: Mapped["ContentPackage"] = relationship(back_populates="items")


class AIUsage(Base):
    __tablename__ = "ai_usage"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    model: Mapped[str] = mapped_column(String(50))
    input_tokens: Mapped[int] = mapped_column(Integer)
    output_tokens: Mapped[int] = mapped_column(Integer)
    cost_usd: Mapped[float] = mapped_column(Float)
    purpose: Mapped[str | None] = mapped_column(String(50))

    user: Mapped["User"] = relationship(back_populates="ai_usage")


__all__ = [
    "Base",
    "Visibility",
    "User",
    "TGAccount",
    "Channel",
    "Subscription",
    "AccountChannelState",
    "Message",
    "MediaAsset",
    "Topic",
    "TopicMessage",
    "Ranking",
    "EditorResult",
    "ImageBrief",
    "ContentPackage",
    "ContentPackageItem",
    "AIUsage",
]
