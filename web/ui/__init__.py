from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from config import settings
from ..routes.auth import get_current_user


templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Render login page with Telegram SSO button."""
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "bot_username": settings.telegram_bot_username or ""},
    )


@router.get("/onboarding", response_class=HTMLResponse)
async def onboarding_page(request: Request, user=Depends(get_current_user)):
    """Render onboarding page with MTProto QR login flow."""
    return templates.TemplateResponse("onboarding.html", {"request": request})


@router.get("/accounts", response_class=HTMLResponse)
async def accounts_page(request: Request, user=Depends(get_current_user)):
    """Render page showing connected MTProto accounts."""
    return templates.TemplateResponse("accounts.html", {"request": request})


@router.get("/subscriptions", response_class=HTMLResponse)
async def subscriptions_page(request: Request, user=Depends(get_current_user)):
    """Render page to manage channel subscriptions."""
    return templates.TemplateResponse("subscriptions.html", {"request": request})


@router.get("/feed", response_class=HTMLResponse)
async def feed_page(request: Request, user=Depends(get_current_user)):
    """Render feed page with messages from subscriptions."""
    return templates.TemplateResponse("feed.html", {"request": request})


@router.get("/top", response_class=HTMLResponse)
async def top_page(request: Request, user=Depends(get_current_user)):
    """Render page for top news and topics."""
    return templates.TemplateResponse("top.html", {"request": request})


@router.get("/packages", response_class=HTMLResponse)
async def packages_page(request: Request, user=Depends(get_current_user)):
    """Render page for publication packages."""
    return templates.TemplateResponse("packages.html", {"request": request})


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, user=Depends(get_current_user)):
    """Render user settings page."""
    return templates.TemplateResponse("settings.html", {"request": request})


@router.get("/usage", response_class=HTMLResponse)
async def usage_page(request: Request, user=Depends(get_current_user)):
    """Render usage and quotas page."""
    return templates.TemplateResponse("usage.html", {"request": request})
