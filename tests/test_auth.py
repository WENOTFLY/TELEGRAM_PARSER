import os
import sys
import types
import hashlib
import hmac
import pathlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    os.environ.update(
        {
            "DATABASE_URL": "sqlite:///./test.db",
            "REDIS_URL": "redis://",
            "OPENAI_API_KEY": "test",
            "SECRET_KEY": "secret",
            "SESSION_KEY_1": "sess",
            "SUPABASE_URL": "supabase",
            "SUPABASE_KEY": "key",
            "SUPABASE_BUCKET": "bucket",
            "FRONTEND_ORIGINS": "https://example.com",
            "TELEGRAM_AUTH_TOKEN": "telegram_token",
        }
    )
    sys.modules["migrate"] = types.SimpleNamespace(upgrade_db=lambda: None)
    sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
    import importlib

    web = importlib.import_module("web")
    from web.routes import auth

    auth.Base.metadata.create_all(auth.engine, tables=[auth.User.__table__])
    client = TestClient(web.app)
    client.db = auth.SessionLocal
    client.User = auth.User
    return client


def _tg_params(data: dict) -> dict:
    token = os.environ["TELEGRAM_AUTH_TOKEN"]
    check = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret = hashlib.sha256(token.encode()).digest()
    h = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    out = data.copy()
    out["hash"] = h
    return out


def test_callback_sets_cookie_and_upserts_user(client: TestClient):
    data = {"id": "1", "username": "alice", "first_name": "Alice", "auth_date": "1"}
    params = _tg_params(data)
    resp = client.get("/auth/telegram/callback", params=params)
    assert resp.status_code == 200
    cookie = resp.headers.get("set-cookie")
    assert "jwt=" in cookie
    assert "HttpOnly" in cookie
    assert "Secure" in cookie
    assert "SameSite=lax" in cookie
    with client.db() as db:
        assert db.query(client.User).filter_by(tg_id=1).first() is not None


def test_invalid_hash_rejected(client: TestClient):
    data = {"id": "2", "username": "bob", "first_name": "Bob", "auth_date": "1", "hash": "bad"}
    resp = client.get("/auth/telegram/callback", params=data)
    assert resp.status_code == 400


def test_logout_clears_cookie(client: TestClient):
    resp = client.post("/auth/logout")
    assert resp.status_code == 200
    cookie = resp.headers.get("set-cookie")
    assert "jwt=" in cookie and "Max-Age=0" in cookie


def test_cors_restricted(client: TestClient):
    allowed = os.environ["FRONTEND_ORIGINS"]
    disallowed = "https://evil.com"
    resp = client.options(
        "/auth/logout",
        headers={"Origin": allowed, "Access-Control-Request-Method": "POST"},
    )
    assert resp.headers.get("access-control-allow-origin") == allowed
    resp = client.options(
        "/auth/logout",
        headers={"Origin": disallowed, "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in resp.headers
