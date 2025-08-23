import os
import sys
import types
import pathlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    os.environ.update(
        {
            "DATABASE_URL": "sqlite:///./channels_test.db",
            "REDIS_URL": "redis://",
            "OPENAI_API_KEY": "test",
            "SECRET_KEY": "secret",
            "SESSION_KEY_1": "sess",
            "SUPABASE_URL": "supabase",
            "SUPABASE_KEY": "key",
            "SUPABASE_BUCKET": "bucket",
            "FRONTEND_ORIGINS": "https://example.com",
            "TELEGRAM_AUTH_TOKEN": "telegram_token",
            "TELEGRAM_API_ID": "1",
            "TELEGRAM_API_HASH": "hash",
        }
    )
    db_path = pathlib.Path("channels_test.db")
    if db_path.exists():
        db_path.unlink()
    sys.modules["migrate"] = types.SimpleNamespace(upgrade_db=lambda: None)
    sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

    import importlib

    for mod in list(sys.modules):
        if mod.startswith("web") or mod == "config":
            del sys.modules[mod]

    web = importlib.import_module("web")
    from web.routes import auth
    from web.models import Base, User, TGAccount, Channel, Subscription

    Base.metadata.create_all(
        auth.engine,
        tables=[User.__table__, TGAccount.__table__, Channel.__table__, Subscription.__table__],
    )

    client = TestClient(web.app)
    client.db = auth.SessionLocal
    client.User = User
    client.TGAccount = TGAccount
    client.Channel = Channel
    client.Subscription = Subscription
    client._encode_jwt = auth._encode_jwt
    return client


class DummyEntity:
    def __init__(self, username: str | None = "testchan", title: str = "Test Channel"):
        self.username = username
        self.title = title


class DummyClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get_entity(self, ident):  # noqa: D401 - simple stub
        return DummyEntity()


def _setup_user(client: TestClient):
    from web.crypto import encrypt_string_session
    from telethon.sessions import StringSession

    with client.db() as db:
        user = client.User(tg_id=1)
        db.add(user)
        db.commit()
        db.refresh(user)
        user_id = user.id

        dummy = StringSession().save()
        cipher, kver = encrypt_string_session(dummy)
        account = client.TGAccount(
            user_id=user_id, session_cipher=cipher, kver=kver, is_active=True
        )
        db.add(account)
        db.commit()

    token = client._encode_jwt({"sub": str(user_id)})
    client.cookies.set("jwt", token)


def test_subscribe_list_and_unsubscribe(client: TestClient, monkeypatch):
    _setup_user(client)
    monkeypatch.setattr("web.routes.channels.TelegramClient", DummyClient)

    resp = client.post("/v1/channels/subscribe", params={"channel": "testchan"})
    assert resp.status_code == 200

    resp = client.get("/v1/channels/my")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["username"] == "testchan"
    assert data[0]["status"] == "public"

    channel_id = data[0]["id"]
    resp = client.delete("/v1/channels/unsubscribe", params={"channel_id": channel_id})
    assert resp.status_code == 200

    resp = client.get("/v1/channels/my")
    assert resp.status_code == 200
    assert resp.json() == []


def test_private_channel_requires_access(client: TestClient, monkeypatch):
    class FailClient(DummyClient):
        async def get_entity(self, ident):
            raise ValueError("no access")

    monkeypatch.setattr("web.routes.channels.TelegramClient", FailClient)

    resp = client.post("/v1/channels/subscribe", params={"channel": "private"})
    assert resp.status_code == 400
