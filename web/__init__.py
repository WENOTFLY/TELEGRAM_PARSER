"""Web service startup configuration."""

import time
import uuid

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    REGISTRY,
    generate_latest,
)

from config import settings
from migrate import upgrade_db
from logging_config import configure_logging, session_id_var, user_id_var
from .routes.auth import _decode_jwt, router as auth_router
from .routes.qr import router as qr_router
from .routes.accounts import router as accounts_router
from .routes.channels import router as channels_router
from .routes.feed import router as feed_router
from .routes.top import router as top_router
from .routes.pipeline import router as pipeline_router
from .routes.usage import router as usage_router
from .ui import router as ui_router

configure_logging()

try:
    REQUEST_COUNT = Counter(
        "http_requests_total", "Total HTTP requests", ["method", "path", "status"]
    )
except ValueError:  # already registered during previous import
    REQUEST_COUNT = REGISTRY._names_to_collectors["http_requests_total"]

try:
    REQUEST_LATENCY = Histogram(
        "http_request_latency_seconds", "Request latency", ["path"]
    )
except ValueError:
    REQUEST_LATENCY = REGISTRY._names_to_collectors["http_request_latency_seconds"]

try:
    HTTP_ERRORS = Counter("http_errors_total", "Total HTTP 5xx responses", ["path"])
except ValueError:
    HTTP_ERRORS = REGISTRY._names_to_collectors["http_errors_total"]


class ContextMiddleware(BaseHTTPMiddleware):
    """Attach user and session identifiers to log context."""

    async def dispatch(self, request: Request, call_next):
        session_token = session_id_var.set(str(uuid.uuid4()))
        user_token = None
        jwt = request.cookies.get("jwt")
        if jwt:
            try:
                payload = _decode_jwt(jwt)
                user_token = user_id_var.set(int(payload.get("sub", 0)))
            except Exception:  # noqa: BLE001 - auth errors not fatal for logs
                pass
        try:
            response = await call_next(request)
        finally:
            session_id_var.reset(session_token)
            if user_token is not None:
                user_id_var.reset(user_token)
        return response


class MetricsMiddleware(BaseHTTPMiddleware):
    """Collect basic Prometheus metrics for requests."""

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        path = request.url.path
        method = request.method
        try:
            response = await call_next(request)
        except Exception:  # noqa: BLE001 - ensure metrics still recorded
            REQUEST_COUNT.labels(method, path, 500).inc()
            HTTP_ERRORS.labels(path).inc()
            REQUEST_LATENCY.labels(path).observe(time.perf_counter() - start)
            raise
        duration = time.perf_counter() - start
        status = response.status_code
        REQUEST_COUNT.labels(method, path, status).inc()
        REQUEST_LATENCY.labels(path).observe(duration)
        if status >= 500:
            HTTP_ERRORS.labels(path).inc()
        return response


app = FastAPI()

origins = [o.strip() for o in settings.frontend_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(ContextMiddleware)
app.add_middleware(MetricsMiddleware)

@app.get("/metrics")
def metrics() -> Response:
    """Expose Prometheus metrics."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

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
