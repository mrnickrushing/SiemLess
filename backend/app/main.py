"""
SiemLess SIEM – FastAPI application entry point.

Startup sequence:
1. Init DB (Alembic upgrade head in prod, create_all in DEBUG)
2. Seed default correlation rules
3. Load rules into correlation engine
4. Start syslog UDP/TCP server (background)
5. Start correlation engine maintenance task

All protected routers are mounted under /api/v1 with JWT auth dependency.
"""
import asyncio
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import AsyncSessionLocal, init_db
from app.deps import get_current_user
from app.routers import alerts, auth, events, ingest, rules, saved_searches, search, stats, threat_intel, watchlists

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)

if not settings.DEBUG:
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown lifecycle."""
    logger.info("Starting SiemLess SIEM v%s", settings.APP_VERSION)

    # 1. Init DB (Alembic in prod, create_all in DEBUG)
    try:
        await init_db()
        logger.info("Database ready")
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

    # 6. Start SLA breach checker
    if settings.SLA_CRITICAL_MINUTES > 0 or settings.SLA_HIGH_MINUTES > 0:
        try:
            asyncio.create_task(
                _sla_check_loop(settings.SLA_CHECK_INTERVAL),
                name="sla-checker",
            )
            logger.info("SLA breach checker started (interval=%ds)", settings.SLA_CHECK_INTERVAL)
        except Exception as exc:
            logger.warning("SLA checker start failed (non-fatal): %s", exc)

    # 7. Start event retention purge task
    if settings.EVENT_RETENTION_DAYS > 0:
        try:
            asyncio.create_task(
                _retention_purge_loop(settings.RETENTION_CHECK_INTERVAL),
                name="retention-purger",
            )
            logger.info(
                "Retention purge task started (retention=%dd, interval=%ds)",
                settings.EVENT_RETENTION_DAYS,
                settings.RETENTION_CHECK_INTERVAL,
            )
        except Exception as exc:
            logger.warning("Retention purge task start failed (non-fatal): %s", exc)

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "Unhandled exception on %s %s: %s",
        request.method,
        request.url.path,
        exc,
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "type": type(exc).__name__},
    )


@app.get("/health", tags=["health"], summary="Health check")
async def health_check() -> dict:
    """Returns service health. No internal detail exposed to callers."""
    import sqlalchemy
    from app.database import engine

    db_ok = True
    try:
        async with engine.connect() as conn:
            await conn.execute(sqlalchemy.text("SELECT 1"))
    except Exception:
        db_ok = False

    return {
        "status": "ok" if db_ok else "degraded",
        "db": db_ok,
    }


async def _sla_check_loop(interval: int) -> None:
    """Periodically mark open alerts that have breached their SLA."""
    import asyncio as _asyncio
    from datetime import timedelta
    from app.models.alert import Alert
    from sqlalchemy import select, update

    while True:
        await _asyncio.sleep(interval)
        try:
            now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
            async with AsyncSessionLocal() as db:
                sla_map = {}
                if settings.SLA_CRITICAL_MINUTES > 0:
                    sla_map["critical"] = timedelta(minutes=settings.SLA_CRITICAL_MINUTES)
                if settings.SLA_HIGH_MINUTES > 0:
                    sla_map["high"] = timedelta(minutes=settings.SLA_HIGH_MINUTES)

                for severity, delta in sla_map.items():
                    breach_time = now - delta
                    await db.execute(
                        update(Alert)
                        .where(
                            Alert.severity == severity,
                            Alert.status.in_(["open", "investigating"]),
                            Alert.sla_breach_at.is_(None),
                            Alert.created_at <= breach_time,
                        )
                        .values(sla_breach_at=now)
                    )
                await db.commit()
        except Exception as exc:
            logger.warning("SLA check error: %s", exc)


async def _retention_purge_loop(interval: int) -> None:
    """Periodically delete security events older than EVENT_RETENTION_DAYS."""
    import asyncio as _asyncio
    from datetime import timedelta
    from sqlalchemy import delete
    from app.models.event import SecurityEvent

    while True:
        await _asyncio.sleep(interval)
        if settings.EVENT_RETENTION_DAYS <= 0:
            continue
        try:
            cutoff = (
                __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
                - timedelta(days=settings.EVENT_RETENTION_DAYS)
            )
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    delete(SecurityEvent).where(SecurityEvent.timestamp < cutoff)
                )
                deleted = result.rowcount
                await db.commit()
            if deleted:
                logger.info("Retention purge: deleted %d events older than %d days", deleted, settings.EVENT_RETENTION_DAYS)
        except Exception as exc:
            logger.warning("Retention purge error: %s", exc)


API_PREFIX = "/api/v1"

_auth = [Depends(get_current_user)]

app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(events.router, prefix=API_PREFIX, dependencies=_auth)
app.include_router(alerts.router, prefix=API_PREFIX, dependencies=_auth)
app.include_router(rules.router, prefix=API_PREFIX, dependencies=_auth)
app.include_router(ingest.router, prefix=API_PREFIX, dependencies=_auth)
app.include_router(search.router, prefix=API_PREFIX, dependencies=_auth)
app.include_router(threat_intel.router, prefix=API_PREFIX, dependencies=_auth)
app.include_router(stats.router, prefix=API_PREFIX, dependencies=_auth)
app.include_router(saved_searches.router, prefix=API_PREFIX, dependencies=_auth)
app.include_router(watchlists.router, prefix=API_PREFIX, dependencies=_auth)


_STATIC_DIR = Path(__file__).parent.parent / "static"


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_spa(full_path: str) -> Response:
    if not _STATIC_DIR.exists():
        return JSONResponse({
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "docs": "/docs",
            "health": "/health",
            "api": API_PREFIX,
        })

    candidate = (_STATIC_DIR / full_path).resolve()
    try:
        candidate.relative_to(_STATIC_DIR.resolve())
    except ValueError:
        return JSONResponse(status_code=400, content={"detail": "Invalid path"})

    if candidate.is_file():
        return FileResponse(candidate)

    index = _STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(index)

    return JSONResponse(status_code=404, content={"detail": "Not found"})
