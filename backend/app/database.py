"""
Database engine, session factory, and startup initialisation.

Startup strategy (production):
  Run `alembic upgrade head` via subprocess so schema changes on existing
  databases are handled correctly. create_all is kept as a DEBUG-only
  fallback for rapid local iteration without a running migration history.
"""
import asyncio
import logging
import os
import subprocess
import sys
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency: provides a per-request async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def _wait_for_db(max_attempts: int = 15, initial_delay: float = 2.0) -> None:
    """Retry connecting to the database until it is reachable."""
    import sqlalchemy

    delay = initial_delay
    for attempt in range(1, max_attempts + 1):
        try:
            async with engine.connect() as conn:
                await conn.execute(sqlalchemy.text("SELECT 1"))
            return
        except Exception as exc:
            if attempt == max_attempts:
                raise
            logger.warning(
                "Database not ready (attempt %d/%d): %s — retrying in %.0fs",
                attempt,
                max_attempts,
                exc,
                delay,
            )
            await asyncio.sleep(delay)
            delay = min(delay * 2, 30)


def _alembic_cmd(alembic_ini: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", alembic_ini, *args],
        capture_output=True,
        text=True,
    )


def _run_alembic_upgrade() -> None:
    """
    Run `alembic upgrade head` in a subprocess.

    We use a subprocess rather than calling Alembic's Python API directly
    because Alembic's async support requires the event loop to not already
    be running (which it is inside FastAPI's lifespan).

    If the upgrade fails because tables already exist (the database was
    previously bootstrapped via create_all or a now-lost migration record),
    we stamp the current state as head and retry — the retry is then a no-op.
    """
    alembic_ini = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "alembic.ini")
    )

    result = _alembic_cmd(alembic_ini, "upgrade", "head")

    if result.returncode != 0:
        stderr = result.stderr or ""
        # Tables exist but alembic_version has no record — stamp then retry.
        if "DuplicateTable" in stderr or "already exists" in stderr:
            logger.warning(
                "Tables already exist but are not stamped in alembic_version. "
                "Stamping head and retrying upgrade."
            )
            stamp = _alembic_cmd(alembic_ini, "stamp", "head")
            if stamp.returncode != 0:
                logger.error("Alembic stamp failed:\n%s", stamp.stderr)
                raise RuntimeError(
                    f"Alembic stamp head failed: {stamp.stderr.strip()[:200]}"
                )
            # Retry — should be a no-op now that the version is recorded.
            result = _alembic_cmd(alembic_ini, "upgrade", "head")
            if result.returncode != 0:
                logger.error("Alembic upgrade failed after stamp:\n%s", result.stderr)
                raise RuntimeError(
                    f"Alembic upgrade head failed: {result.stderr.strip()[:200]}"
                )
        else:
            logger.error("Alembic upgrade failed:\n%s", stderr)
            raise RuntimeError(
                f"Alembic upgrade head failed: {stderr.strip()[:200]}"
            )

    if result.stdout:
        logger.info("Alembic: %s", result.stdout.strip())


async def init_db() -> None:
    """
    Initialise the database schema.

    Production (DEBUG=False): wait for DB readiness, then run Alembic
    migrations via `alembic upgrade head`. This is safe to call on every
    startup — Alembic is idempotent when already at head.

    Development (DEBUG=True): fall back to SQLAlchemy create_all for
    speed. Alembic is still available but not enforced.
    """
    await _wait_for_db()

    if settings.DEBUG:
        logger.warning(
            "DEBUG mode: using create_all instead of Alembic migrations. "
            "Do NOT use this in production."
        )
        # Import models so Base.metadata is populated
        from app.models import alert, event, rule, threat_intel  # noqa: F401

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        return

    logger.info("Running Alembic migrations (upgrade head)…")
    await asyncio.get_event_loop().run_in_executor(None, _run_alembic_upgrade)
    logger.info("Alembic migrations complete")
