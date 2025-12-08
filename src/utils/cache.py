"""Caching utilities using Redis."""

import hashlib
import json
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any, ParamSpec, TypeVar

import redis

from src.config import get_settings
from src.utils.logging import get_logger

logger = get_logger(__name__)

P = ParamSpec("P")
T = TypeVar("T")

# Lazy redis client initialization
_redis_client: redis.Redis | None = None


def get_redis_client() -> redis.Redis:
    """Get or create Redis client."""
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


def _make_cache_key(prefix: str, *args: Any, **kwargs: Any) -> str:
    """Generate a cache key from function arguments."""
    key_data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
    key_hash = hashlib.sha256(key_data.encode()).hexdigest()[:16]
    return f"{prefix}:{key_hash}"


def cached(
    prefix: str,
    ttl_seconds: int | None = None,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    Decorator to cache function results in Redis.

    Args:
        prefix: Cache key prefix
        ttl_seconds: Time to live in seconds (uses default from settings if None)
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            settings = get_settings()
            ttl = ttl_seconds or settings.cache_ttl_seconds
            cache_key = _make_cache_key(prefix, *args, **kwargs)

            try:
                client = get_redis_client()
                cached_value = client.get(cache_key)
                if cached_value is not None:
                    logger.debug("cache_hit", key=cache_key)
                    return json.loads(cached_value)
            except redis.RedisError as e:
                logger.warning("cache_read_error", error=str(e), key=cache_key)

            result = func(*args, **kwargs)

            try:
                client = get_redis_client()
                client.setex(cache_key, ttl, json.dumps(result, default=str))
                logger.debug("cache_set", key=cache_key, ttl=ttl)
            except redis.RedisError as e:
                logger.warning("cache_write_error", error=str(e), key=cache_key)

            return result

        return wrapper

    return decorator


def cached_async(
    prefix: str,
    ttl_seconds: int | None = None,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """
    Async decorator to cache function results in Redis.

    Args:
        prefix: Cache key prefix
        ttl_seconds: Time to live in seconds (uses default from settings if None)
    """

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            settings = get_settings()
            ttl = ttl_seconds or settings.cache_ttl_seconds
            cache_key = _make_cache_key(prefix, *args, **kwargs)

            try:
                client = get_redis_client()
                cached_value = client.get(cache_key)
                if cached_value is not None:
                    logger.debug("cache_hit", key=cache_key)
                    return json.loads(cached_value)
            except redis.RedisError as e:
                logger.warning("cache_read_error", error=str(e), key=cache_key)

            result = await func(*args, **kwargs)

            try:
                client = get_redis_client()
                client.setex(cache_key, ttl, json.dumps(result, default=str))
                logger.debug("cache_set", key=cache_key, ttl=ttl)
            except redis.RedisError as e:
                logger.warning("cache_write_error", error=str(e), key=cache_key)

            return result

        return wrapper

    return decorator


def invalidate_cache(pattern: str) -> int:
    """
    Invalidate cache keys matching a pattern.

    Args:
        pattern: Redis key pattern (e.g., "linear:*")

    Returns:
        Number of keys deleted
    """
    try:
        client = get_redis_client()
        keys = list(client.scan_iter(match=pattern))
        if keys:
            deleted = client.delete(*keys)
            logger.info("cache_invalidated", pattern=pattern, count=deleted)
            return deleted
        return 0
    except redis.RedisError as e:
        logger.error("cache_invalidate_error", error=str(e), pattern=pattern)
        return 0
