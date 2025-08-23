import os
import sys
import types
import pathlib
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    os.environ.update(
        {
            "DATABASE_URL": "sqlite:///./feed_top.db",
            "REDIS_URL": "redis://",
            "OPENAI_API_KEY": "test",
            "SECRET_KEY": "secret",
            "SESSION_KEY_1": "sess",
            "SUPABASE_URL": "supabase",
            "SUPABASE_KEY": "key",
            "SUPABASE_BUCKET": "bucket",
            "FRONTEND_ORIGINS": "https://example.com",
        }
    )
    db_path = pathlib.Path("feed_top.db")
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
    from web.models import (
        Base,
        User,
        Channel,
        Subscription,
        Message,
        Ranking,
        Topic,
    )

    Base.metadata.create_all(
        auth.engine,
        tables=[
            User.__table__,
            Channel.__table__,
            Subscription.__table__,
            Message.__table__,
            Ranking.__table__,
            Topic.__table__,
        ],
    )

    client = TestClient(web.app)
    client.db = auth.SessionLocal
    client.User = User
    client.Channel = Channel
    client.Subscription = Subscription
    client.Message = Message
    client.Ranking = Ranking
    client.Topic = Topic
    client._encode_jwt = auth._encode_jwt
    _setup_data(client)
    return client


def _setup_data(client: TestClient):
    with client.db() as db:
        user = client.User(tg_id=1)
        db.add(user)
        db.commit()
        db.refresh(user)
        user_id = user.id

        channel = client.Channel(username="test", title="Test")
        db.add(channel)
        db.commit()
        db.refresh(channel)
        channel_id = channel.id

        db.add(client.Subscription(user_id=user_id, channel_id=channel_id))

        msg1 = client.Message(
            channel_id=channel.id,
            msg_id=1,
            date=datetime.utcnow() - timedelta(days=2),
            text="hello",
            type="text",
            lang="en",
        )
        msg2 = client.Message(
            channel_id=channel.id,
            msg_id=2,
            date=datetime.utcnow() - timedelta(days=1),
            text="hola",
            type="photo",
            lang="es",
        )
        db.add_all([msg1, msg2])
        db.commit()
        db.refresh(msg1)
        db.refresh(msg2)
        msg2_date = msg2.date

        topic = client.Topic(title="Topic")
        db.add(topic)
        db.commit()
        db.refresh(topic)

        r1 = client.Ranking(
            entity_kind="message", entity_id=msg1.id, window="24h", score=5
        )
        r2 = client.Ranking(
            entity_kind="topic", entity_id=topic.id, window="24h", score=10
        )
        db.add_all([r1, r2])
        db.commit()

    token = client._encode_jwt({"sub": str(user_id)})
    client.cookies.set("jwt", token)
    client.channel_id = channel_id
    client.msg2_date = msg2_date


def test_feed_filters(client: TestClient):
    resp = client.get("/v1/feed")
    assert resp.status_code == 200
    assert len(resp.json()) == 2

    resp = client.get("/v1/feed", params={"lang": "en"})
    assert len(resp.json()) == 1

    resp = client.get("/v1/feed", params={"type": "photo"})
    data = resp.json()
    assert len(data) == 1
    assert data[0]["type"] == "photo"

    resp = client.get(
        "/v1/feed", params={"date_from": client.msg2_date.isoformat()}
    )
    data = resp.json()
    assert len(data) == 1
    assert data[0]["msg_id"] == 2

    resp = client.get("/v1/feed", params={"channel_id": client.channel_id})
    assert len(resp.json()) == 2


def test_top_rankings(client: TestClient):
    resp = client.get("/v1/top", params={"window": "24h", "by": "message"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["score"] == 5

    resp = client.get("/v1/top", params={"window": "24h", "by": "topic"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["score"] == 10
