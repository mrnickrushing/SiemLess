"""
Async Redis client wrapper.

Provides a shared connection pool used by the correlation engine (alert
pub/sub) and the health endpoint. Designed to fail gracefully — if Redis
is unavailable the application continues to work, Redis-backed features
just silently no-op.

Usage:
    from app.services.redis_client import redis_client

    await redis_client.publish("siemless:alerts", json.dumps(payload))
    ok = await redis_client.ping()
"""
import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    import redis.asyncio as aioredis
    _REDIS_AVAILABLE = True
except ImportError:
    _REDIS_AVAILABLE = False
    logger.warning("redis package not available — Redis features disabled.")


class _NoopRedis:
    """Drop-in no-op used when Redis is not available or unreachable."""

    async def ping(self) -> bool:
        return False

    async def get(self, key: str) -> None:
        return None

    async def set(self, key: str, value: Any, ex: Optional[int] = None) -> None:
        pass

    async def delete(self, *keys: str) -> None:
        pass

    async def publish(self, channel: str, message: str) -> None:
        pass

    async def close(self) -> None:
        pass


class RedisClient:
    """
    Thin async wrapper around redis.asyncio with graceful degradation.

    On first use the client attempts to connect. If Redis is not reachable
    (connection refused, timeout, etc.) it falls back to _NoopRedis and
    logs a warning. Subsequent calls are no-ops — the app keeps running.
    """

    def __init__(self, url: str) -> None:
        self._url = url
        self._client: Any = None
        self._available: Optional[bool] = None  # None = not yet probed

    async def _get_client(self) -> Any:
        if self._available is False:
            return _NoopRedis()
        if self._client is None:
            if not _REDIS_AVAILABLE:
                self._available = False
                return _NoopRedis()
            try:
                self._client = aioredis.from_url(
                    self._url,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=2,
                    socket_timeout=2,
                    retry_on_timeout=False,
                )
                await self._client.ping()
                self._available = True
                logger.info("Redis connected: %s", self._url)
            except Exception as exc:
                logger.warning(
                    "Redis unavailable (%s) — alert pub/sub and caching disabled.",
                    exc,
                )
                self._client = None
                self._available = False
                return _NoopRedis()
        return self._client

    async def ping(self) -> bool:
        try:
            client = await self._get_client()
            if isinstance(client, _NoopRedis):
                return False
            await client.ping()
            return True
        except Exception:
            return False

    async def get(self, key: str) -> Optional[str]:
        try:
            client = await self._get_client()
            return await client.get(key)
        except Exception as exc:
            logger.debug("Redis GET %s failed: %s", key, exc)
            return None

    async def set(self, key: str, value: Any, ex: Optional[int] = None) -> None:
        try:
            client = await self._get_client()
            await client.set(key, value, ex=ex)
        except Exception as exc:
            logger.debug("Redis SET %s failed: %s", key, exc)

    async def set_json(self, key: str, value: Any, ex: Optional[int] = None) -> None:
        await self.set(key, json.dumps(value), ex=ex)

    async def get_json(self, key: str) -> Optional[Any]:
        raw = await self.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    async def delete(self, *keys: str) -> None:
        try:
            client = await self._get_client()
            await client.delete(*keys)
        except Exception as exc:
            logger.debug("Redis DELETE failed: %s", exc)

    async def publish(self, channel: str, message: str) -> None:
        """Publish a message to a Redis pub/sub channel."""
        try:
            client = await self._get_client()
            await client.publish(channel, message)
        except Exception as exc:
            logger.debug("Redis PUBLISH %s failed: %s", channel, exc)

    async def close(self) -> None:
        if self._client is not None and not isinstance(self._client, _NoopRedis):
            try:
                await self._client.aclose()
            except Exception:
                pass
            self._client = None
        self._available = None


# ---------------------------------------------------------------------------
# Module-level singleton — import this everywhere
# ---------------------------------------------------------------------------
from app.config import settings as _settings  # noqa: E402

redis_client = RedisClient(_settings.REDIS_URL)
