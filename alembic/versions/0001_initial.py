"""initial database schema"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


visibility_enum = sa.Enum("public", "private", name="visibility")


def upgrade() -> None:
    visibility_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tg_id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=255)),
        sa.Column("first_name", sa.String(length=255)),
        sa.Column("last_name", sa.String(length=255)),
        sa.Column("photo_url", sa.String()),
        sa.Column("role", sa.String(length=50)),
        sa.Column("plan", sa.String(length=50)),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_tg_id", "users", ["tg_id"], unique=True)

    op.create_table(
        "tg_accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("session_cipher", sa.Text(), nullable=False),
        sa.Column("phone", sa.String(length=32)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("kver", sa.Integer()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "channels",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=255)),
        sa.Column("title", sa.String(length=255)),
        sa.Column("visibility", visibility_enum, nullable=False, server_default="public"),
        sa.Column("owner_account_id", sa.Integer(), sa.ForeignKey("tg_accounts.id")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_parsed_at", sa.DateTime()),
    )
    op.create_index("ix_channels_username", "channels", ["username"], unique=True)

    op.create_table(
        "subscriptions",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("channel_id", sa.Integer(), sa.ForeignKey("channels.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("added_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "account_channel_state",
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("tg_accounts.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("channel_id", sa.Integer(), sa.ForeignKey("channels.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("last_msg_id", sa.Integer()),
    )

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("channel_id", sa.Integer(), sa.ForeignKey("channels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("msg_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.DateTime(), nullable=False),
        sa.Column("text", sa.Text()),
        sa.Column("author", sa.String(length=255)),
        sa.Column("views", sa.Integer()),
        sa.Column("reactions", sa.Integer()),
        sa.Column("forwards", sa.Integer()),
        sa.Column("comments", sa.Integer()),
        sa.Column("lang", sa.String(length=16)),
        sa.Column("type", sa.String(length=50)),
        sa.Column("hashtags", postgresql.ARRAY(sa.String()), server_default=sa.text("'{}'")),
        sa.Column("links", postgresql.ARRAY(sa.String()), server_default=sa.text("'{}'")),
        sa.Column("media_present", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.UniqueConstraint("channel_id", "msg_id", name="uq_messages_channel_msg"),
    )

    op.create_table(
        "media_assets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("message_id", sa.Integer(), sa.ForeignKey("messages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(length=50), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("size", sa.Integer()),
        sa.Column("format", sa.String(length=50)),
        sa.Column("hash", sa.String(length=128)),
    )

    op.create_table(
        "topics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "topic_messages",
        sa.Column("topic_id", sa.Integer(), sa.ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("message_id", sa.Integer(), sa.ForeignKey("messages.id", ondelete="CASCADE"), primary_key=True),
    )

    op.create_table(
        "ranking",
        sa.Column("entity_kind", sa.String(length=50), primary_key=True),
        sa.Column("entity_id", sa.Integer(), primary_key=True),
        sa.Column("window", sa.String(length=10), primary_key=True),
        sa.Column("score", sa.Float()),
        sa.Column("indexed", sa.DateTime()),
    )

    op.create_table(
        "editor_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("topic_id", sa.Integer(), sa.ForeignKey("topics.id")),
        sa.Column("message_ids", postgresql.ARRAY(sa.Integer())),
        sa.Column("language", sa.String(length=16)),
        sa.Column("headline", sa.Text()),
        sa.Column("dek", sa.Text()),
        sa.Column("body_variants", postgresql.JSONB()),
        sa.Column("key_points", postgresql.JSONB()),
        sa.Column("source_links", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "image_briefs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("editor_result_id", sa.Integer(), sa.ForeignKey("editor_results.id", ondelete="CASCADE")),
        sa.Column("title", sa.String(length=255)),
        sa.Column("prompt", sa.Text()),
        sa.Column("negative", sa.Text()),
        sa.Column("size", sa.String(length=50)),
        sa.Column("variants", sa.Integer()),
        sa.Column("caption", sa.Text()),
        sa.Column("style_tags", postgresql.ARRAY(sa.String())),
    )

    op.create_table(
        "content_packages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("editor_result_id", sa.Integer(), sa.ForeignKey("editor_results.id", ondelete="CASCADE")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "content_package_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("package_id", sa.Integer(), sa.ForeignKey("content_packages.id", ondelete="CASCADE")),
        sa.Column("platform", sa.String(length=50)),
        sa.Column("post_time", sa.DateTime()),
        sa.Column("post_text", postgresql.JSONB()),
        sa.Column("hashtags", postgresql.ARRAY(sa.String())),
        sa.Column("cta", sa.String(length=255)),
        sa.Column("image_url", sa.String()),
    )

    op.create_table(
        "ai_usage",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("ts", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("model", sa.String(length=50), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Float(), nullable=False),
        sa.Column("purpose", sa.String(length=50)),
    )


def downgrade() -> None:
    op.drop_table("ai_usage")
    op.drop_table("content_package_items")
    op.drop_table("content_packages")
    op.drop_table("image_briefs")
    op.drop_table("editor_results")
    op.drop_table("ranking")
    op.drop_table("topic_messages")
    op.drop_table("topics")
    op.drop_table("media_assets")
    op.drop_table("messages")
    op.drop_table("account_channel_state")
    op.drop_table("subscriptions")
    op.drop_index("ix_channels_username", table_name="channels")
    op.drop_table("channels")
    op.drop_table("tg_accounts")
    op.drop_index("ix_users_tg_id", table_name="users")
    op.drop_table("users")
    visibility_enum.drop(op.get_bind(), checkfirst=True)
