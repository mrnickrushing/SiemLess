"""
SiemLess SIEM – FastAPI application entry point.

Startup sequence:
1. Create DB tables (idempotent via create_all)
2. Seed default correlation rules
3. Load rules into correlation engine
4. Start syslog UDP/TCP server (background)
5. Start correlation engine maintenance task

All routers are mounted under /api/v1.
"""
import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import AsyncSessionLocal, init_db

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)

# Suppress noisy SQLAlchemy echo logs unless DEBUG
if not settings.DEBUG:
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown lifecycle."""
    # ---- STARTUP ----
    logger.info("Starting SiemLess SIEM v%s", settings.APP_VERSION)

    # 1. Initialize DB tables
    try:
        await init_db()
        logger.info("Database tables initialised")
    except Exception as exc:
        logger.error("Failed to initialise database: %s", exc)
        raise

    # 2. Seed default correlation rules
    try:
        from app.services.correlation import seed_default_rules
        async with AsyncSessionLocal() as db:
            await seed_default_rules(db)
    except Exception as exc:
        logger.warning("Rule seeding failed (non-fatal): %s", exc)

    # 3. Load rules into correlation engine
    try:
        from app.services.correlation import correlation_engine
        async with AsyncSessionLocal() as db:
            await correlation_engine.load_rules(db)
        logger.info("Correlation engine rules loaded")
    except Exception as exc:
        logger.warning("Correlation engine rule loading failed (non-fatal): %s", exc)

    # 4. Start syslog server
    if settings.SYSLOG_ENABLED:
        try:
            from app.services.syslog_server import syslog_server
            await syslog_server.start(host=settings.SYSLOG_HOST, port=settings.SYSLOG_PORT)
            logger.info(
                "Syslog server started on %s:%d", settings.SYSLOG_HOST, settings.SYSLOG_PORT
            )
        except Exception as exc:
            logger.warning("Syslog server failed to start (non-fatal): %s", exc)

    # 5. Start correlation engine cleanup task
    try:
        from app.services.correlation import correlation_engine
        await correlation_engine.start_cleanup_task(
            interval_seconds=settings.CORRELATION_WINDOW_CLEANUP_INTERVAL
        )
    except Exception as exc:
        logger.warning("Correlation cleanup task start failed (non-fatal): %s", exc)

    logger.info("SiemLess startup complete")

    yield

    # ---- SHUTDOWN ----
    logger.info("Shutting down SiemLess…")

    try:
        from app.services.syslog_server import syslog_server
        await syslog_server.stop()
    except Exception as exc:
        logger.warning("Error stopping syslog server: %s", exc)

    try:
        from app.services.correlation import correlation_engine
        correlation_engine.stop_cleanup_task()
    except Exception as exc:
        logger.warning("Error stopping correlation engine: %s", exc)

    try:
        from app.services.threat_intel import threat_intel_service
        await threat_intel_service.close()
    except Exception as exc:
        logger.warning("Error closing threat intel HTTP client: %s", exc)

    try:
        from app.services.alerting import alert_service
        await alert_service.close()
    except Exception as exc:
        logger.warning("Error closing alerting HTTP client: %s", exc)

    logger.info("SiemLess shutdown complete")


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="SiemLess SIEM API",
    description=(
        "Security Information and Event Management (SIEM) REST API. "
        "Provides log ingestion, event search, correlation rules, alerting, "
        "and threat intelligence integration."
    ),
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request logging middleware
# ---------------------------------------------------------------------------

@app.middleware("http")
async def request_logging_middleware(request: Request, call_next) -> Response:
    start_time = time.perf_counter()
    response = await call_next(request)
    elapsed = (time.perf_counter() - start_time) * 1000
    logger.info(
        "%s %s %d %.1fms",
        request.method,
        request.url.path,
        response.status_code,
        elapsed,
    )
    response.headers["X-Process-Time-Ms"] = f"{elapsed:.1f}"
    return response


# ---------------------------------------------------------------------------
# Global exception handler
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled exception on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "type": type(exc).__name__},
    )


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health", tags=["health"], summary="Health check endpoint")
async def health_check() -> dict:
    """Returns application health status."""
    from app.database import engine

    db_status = "ok"
    try:
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
    except Exception as exc:
        db_status = f"error: {exc}"

    from app.services.correlation import correlation_engine
    from app.services.syslog_server import syslog_server

    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "version": settings.APP_VERSION,
        "database": db_status,
        "syslog_server": "running" if syslog_server.is_running else "stopped",
        "correlation_rules_loaded": len(correlation_engine._rules),
        "syslog_enabled": settings.SYSLOG_ENABLED,
    }


# ---------------------------------------------------------------------------
# Mount routers
# ---------------------------------------------------------------------------

API_PREFIX = "/api/v1"

from app.routers import events, alerts, rules, ingest, search, threat_intel, stats  # noqa: E402

app.include_router(events.router, prefix=API_PREFIX)
app.include_router(alerts.router, prefix=API_PREFIX)
app.include_router(rules.router, prefix=API_PREFIX)
app.include_router(ingest.router, prefix=API_PREFIX)
app.include_router(search.router, prefix=API_PREFIX)
app.include_router(threat_intel.router, prefix=API_PREFIX)
app.include_router(stats.router, prefix=API_PREFIX)


# ---------------------------------------------------------------------------
# Root redirect
# ---------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
async def root() -> dict:
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health",
        "api": API_PREFIX,
    }
