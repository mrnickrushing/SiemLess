"""
SiemLess FastAPI application entry point.

Initialises the FastAPI instance, configures CORS and middleware, registers
all API routers, starts background services (syslog, correlation engine), and
serves the React SPA for any unmatched routes.
"""
import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routers import alerts, auth, auth_oidc, events, ingest, rules, saved_searches, search, stats, threat_intel
from app.routers import watchlists
from app.routers import cases, compliance, ueba, connectors, retention, playbooks, assets, admin, integrations, threat_feeds
from app.services.correlation import correlation_engine
from app.services.syslog_server import syslog_server
from app.services.kafka_consumer import kafka_consumer_service

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


# ---------------------------------------------------------------------------
# Lifespan: startup and shutdown hooks
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Start background services on startup; shut them down on exit."""
    # Start correlation engine window-counter cleanup task
    if settings.CORRELATION_ENABLED:
        await correlation_engine.start_cleanup_task(
            interval_seconds=settings.CORRELATION_WINDOW_CLEANUP_INTERVAL
        )
        logger.info("Correlation engine started")

    # Start syslog server (UDP + TCP listeners)
    if settings.SYSLOG_ENABLED:
        try:
            await syslog_server.start(
                host=settings.SYSLOG_HOST,
                port=settings.SYSLOG_PORT,
            )
        except Exception as exc:  # pragma: no cover
            logger.warning("Syslog server failed to start: %s", exc)

    # Start Kafka consumer (no-op if KAFKA_BOOTSTRAP_SERVERS not set)
    try:
        await kafka_consumer_service.start()
    except Exception as exc:
        logger.warning("Kafka consumer failed to start: %s", exc)

    # Start cloud connector manager
    try:
        from app.services.connectors.manager import connector_manager
        await connector_manager.start()
    except Exception as exc:
        logger.warning("Connector manager failed to start: %s", exc)

    # Start UEBA baseline loop
    try:
        if getattr(settings, "UEBA_ENABLED", False):
            from app.services.baseline import baseline_service
            await baseline_service.start_baseline_loop()
    except Exception as exc:
        logger.warning("UEBA baseline loop failed to start: %s", exc)

    # Start retention service loop
    try:
        from app.services.retention import retention_service
        await retention_service.start_retention_loop()
    except Exception as exc:
        logger.warning("Retention service failed to start: %s", exc)

    # Start threat feed manager
    try:
        from app.services.feed_connectors.manager import feed_manager
        await feed_manager.start()
    except Exception as exc:
        logger.warning("Threat feed manager failed to start: %s", exc)

    yield

    # Shutdown
    await kafka_consumer_service.stop()

    if settings.SYSLOG_ENABLED and syslog_server.is_running:
        await syslog_server.stop()
        logger.info("Syslog server stopped")

    if settings.CORRELATION_ENABLED:
        correlation_engine.stop_cleanup_task()
        logger.info("Correlation engine stopped")


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# API routers  (all prefixed under /api)
# ---------------------------------------------------------------------------

_API_PREFIX = "/api/v1"

app.include_router(auth.router, prefix=_API_PREFIX)
app.include_router(auth_oidc.router, prefix=_API_PREFIX)
app.include_router(events.router, prefix=_API_PREFIX)
app.include_router(alerts.router, prefix=_API_PREFIX)
app.include_router(rules.router, prefix=_API_PREFIX)
app.include_router(ingest.router, prefix=_API_PREFIX)
app.include_router(search.router, prefix=_API_PREFIX)
app.include_router(stats.router, prefix=_API_PREFIX)
app.include_router(threat_intel.router, prefix=_API_PREFIX)
app.include_router(saved_searches.router, prefix=_API_PREFIX)
app.include_router(watchlists.router, prefix=_API_PREFIX)
app.include_router(cases.router, prefix=_API_PREFIX)
app.include_router(compliance.router, prefix=_API_PREFIX)
app.include_router(ueba.router, prefix=_API_PREFIX)
app.include_router(connectors.router, prefix=_API_PREFIX)
app.include_router(retention.router, prefix=_API_PREFIX)
app.include_router(playbooks.router, prefix=_API_PREFIX)
app.include_router(assets.router, prefix=_API_PREFIX)
app.include_router(admin.router, prefix=_API_PREFIX)
app.include_router(integrations.router, prefix=_API_PREFIX)
app.include_router(threat_feeds.router, prefix=_API_PREFIX)

# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health", tags=["health"], summary="Health check")
async def health_check() -> JSONResponse:
    """Returns service liveness status and basic component states."""
    return JSONResponse(
        content={
            "status": "ok",
            "version": settings.APP_VERSION,
            "syslog": {"running": syslog_server.is_running},
        }
    )

# ---------------------------------------------------------------------------
# React SPA — static files and catch-all fallback
# ---------------------------------------------------------------------------

_STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")

if os.path.isdir(_STATIC_DIR):
    # Mount assets (JS, CSS, images) at /static so they are served directly.
    _ASSETS_DIR = os.path.join(_STATIC_DIR, "assets")
    if os.path.isdir(_ASSETS_DIR):
        app.mount("/assets", StaticFiles(directory=_ASSETS_DIR), name="assets")

    app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

    _INDEX_HTML = os.path.join(_STATIC_DIR, "index.html")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(request: Request, full_path: str) -> FileResponse:
        """Serve index.html for all unmatched routes so the React router works."""
        return FileResponse(_INDEX_HTML)
else:
    logger.warning(
        "Static directory '%s' not found — React frontend will not be served. "
        "Build the frontend and place the output in backend/static/.",
        _STATIC_DIR,
    )
