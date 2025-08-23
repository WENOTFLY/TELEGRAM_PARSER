"""Web service startup configuration."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from migrate import upgrade_db
from .routes.auth import router as auth_router
from .routes.qr import router as qr_router
from .routes.accounts import router as accounts_router
from .routes.channels import router as channels_router
from .routes.feed import router as feed_router
from .routes.top import router as top_router
from .routes.pipeline import router as pipeline_router
from .routes.usage import router as usage_router
from .ui import router as ui_router

app = FastAPI()

origins = [o.strip() for o in settings.frontend_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(qr_router)
app.include_router(accounts_router)
app.include_router(channels_router)
app.include_router(feed_router)
app.include_router(top_router)
app.include_router(pipeline_router)
app.include_router(usage_router)
app.include_router(ui_router)

upgrade_db()
