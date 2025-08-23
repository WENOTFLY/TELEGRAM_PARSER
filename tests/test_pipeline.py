import os
import sys
import types
import pathlib
from datetime import datetime

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    os.environ.update(
        {
            "DATABASE_URL": "sqlite:///./pipeline.db",
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
    db_path = pathlib.Path("pipeline.db")
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
        EditorResult,
        ImageBrief,
        MediaAsset,
        ContentPackage,
        ContentPackageItem,
    )

    Base.metadata.create_all(
        auth.engine,
        tables=[
            User.__table__,
            EditorResult.__table__,
            ImageBrief.__table__,
            MediaAsset.__table__,
            ContentPackage.__table__,
            ContentPackageItem.__table__,
        ],
    )

    client = TestClient(web.app)
    client.db = auth.SessionLocal
    client.User = User
    client.EditorResult = EditorResult
    client.ImageBrief = ImageBrief
    client.MediaAsset = MediaAsset
    client.ContentPackage = ContentPackage
    client.ContentPackageItem = ContentPackageItem
    client._encode_jwt = auth._encode_jwt

    with client.db() as db:
        user = User(tg_id=1)
        db.add(user)
        db.commit()
        db.refresh(user)
        token = client._encode_jwt({"sub": str(user.id)})
    client.cookies.set("jwt", token)
    return client


def test_pipeline_flow(client: TestClient, monkeypatch):
    # 1. create transform
    payload = {
        "headline": "Headline",
        "body_variants": {"short": "s"},
        "source_links": ["http://src"],
    }
    resp = client.post("/v1/transform", json=payload)
    assert resp.status_code == 200
    transform_id = resp.json()["id"]

    # 2. image brief
    brief_payload = {
        "editor_result_id": transform_id,
        "prompt": "A cat"
    }
    resp = client.post("/v1/image-brief", json=brief_payload)
    assert resp.status_code == 200
    brief_id = resp.json()["id"]

    # patch OpenAI client
    class DummyImages:
        def generate(self, **kwargs):
            return types.SimpleNamespace(
                data=[types.SimpleNamespace(url="http://img1")]
            )

    class DummyModerations:
        def create(self, **kwargs):
            return types.SimpleNamespace(results=[types.SimpleNamespace(flagged=False)])

    class DummyClient:
        def __init__(self, *args, **kwargs):
            self.images = DummyImages()
            self.moderations = DummyModerations()

    import web.routes.pipeline as pipeline

    monkeypatch.setattr(pipeline, "OpenAI", lambda: DummyClient())

    resp = client.post("/v1/images", json={"image_brief_id": brief_id})
    assert resp.status_code == 200
    assert resp.json()["urls"] == ["http://img1"]

    with client.db() as db:
        count = db.query(client.MediaAsset).count()
        assert count == 1

    # 3. package
    pkg_payload = {
        "editor_result_id": transform_id,
        "items": [
            {
                "platform": "tg",
                "post_time": datetime.utcnow().isoformat(),
                "post_text": {"short": "s"},
                "hashtags": ["#tg"],
                "cta": "read",
                "image_url": "http://img1",
            }
        ],
    }
    resp = client.post("/v1/package", json=pkg_payload)
    assert resp.status_code == 200
    package_id = resp.json()["id"]

    resp = client.get("/v1/packages")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["id"] == package_id
    assert data[0]["items"][0]["platform"] == "tg"
