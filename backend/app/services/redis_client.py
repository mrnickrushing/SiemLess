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
        """
        Store a value in Redis under the given key, optionally setting a time-to-live.
        
        Parameters:
            key (str): Redis key under which to store the value.
            value (Any): Value to store; callers are responsible for serialization if needed.
            ex (Optional[int]): Expiration time in seconds; if provided, the key will expire after this many seconds.
        
        Notes:
            - If Redis is unavailable or an error occurs, the operation is silently ignored (no exception is raised).
        """
        pass

    async def setex(self, key: str, ttl: int, value: Any) -> None:
        """
        Set a key to the given value with a time-to-live in seconds.
        
        This stores `value` under `key` and ensures the key expires after `ttl` seconds.
        If Redis is unavailable or an error occurs, the operation is silently ignored.
        
        Parameters:
            key (str): The Redis key to set.
            ttl (int): Time-to-live in seconds for the key.
            value (Any): The value to store under the key.
        """
        pass

    async def delete(self, *keys: str) -> None:
        """
        Delete one or more keys from the Redis store.
        
        Attempts to remove each provided key; if Redis is unavailable or an error occurs during deletion, the error is suppressed and the operation becomes a no-op.
        
        Parameters:
            *keys (str): One or more Redis key names to delete.
        """
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
        """
        Set a Redis key to the given value with an optional time-to-live.
        
        Parameters:
            key (str): The Redis key to set.
            value (Any): The value to store under the key; will be passed through to the client as-is.
            ex (Optional[int]): Time-to-live in seconds; if provided, the key will expire after this many seconds.
        
        Notes:
            Any errors contacting Redis are suppressed; failures are logged at debug level and not raised.
        """
        try:
            client = await self._get_client()
            await client.set(key, value, ex=ex)
        except Exception as exc:
            logger.debug("Redis SET %s failed: %s", key, exc)

    async def setex(self, key: str, ttl: int, value: Any) -> None:
        """
        Set a value for the given key and ensure it expires after the specified TTL.
        
        Parameters:
            key (str): Redis key to set.
            ttl (int): Time-to-live in seconds after which the key expires.
            value (Any): Value to store.
        """
        await self.set(key, value, ex=ttl)

    async def set_json(self, key: str, value: Any, ex: Optional[int] = None) -> None:
        """
        Store a Python object as a JSON-encoded value in Redis under the given key with an optional TTL.
        
        Parameters:
            key (str): Redis key to set.
            value (Any): JSON-serializable Python object to store.
            ex (Optional[int]): Expiration time in seconds; if provided, the key will expire after this many seconds.
        """
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


async def get_redis() -> RedisClient:
    """
    Get the module-level shared Redis client for dependency injection.
    
    Returns:
        redis_client (RedisClient): The singleton RedisClient instance used by the application.
    """
    return redis_client
