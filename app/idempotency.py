"""Idempotency store for mutating endpoints (submit_job, update_job).

Behaviour by Idempotency-Key header:
  - No header         -> pass through, normal execution every time.
  - First request     -> lock key, run handler, cache 200 response, return it.
  - Retry same key    -> return cached response without calling the adapter again.
  - In-flight same key -> 409 Conflict (Retry-After: 2).
  - Same key, different body -> 422 Unprocessable Entity.
  - Adapter raises    -> lock is released; client may retry safely.

Backing stores:
  - InMemoryIdempotencyStore  : in-process dict; dev/single-instance only.
  - RedisIdempotencyStore     : Redis-backed; required for multi-replica.

Select via REDIS_URL env var (see config.py).  Install redis extras when using
Redis: pip install -e ".[redis]"
"""
import os
import hashlib
import json
import logging
import time

import redis.asyncio as aioredis

log = logging.getLogger(__name__)

_LOCK_PREFIX = "LOCKED:"
_DONE_PREFIX = "DONE:"
_LOCK_TTL_SECONDS = int(os.environ.get("LOCK_TTL_SECONDS", 60))  # max seconds a handler may hold the lock before it is considered dead


def build_cache_key(user_id: str, idempotency_key: str, endpoint: str) -> str:
    """Produce a scoped, opaque cache key from user + key + endpoint."""
    raw = f"{user_id}:{endpoint}:{idempotency_key}"
    return hashlib.sha256(raw.encode()).hexdigest()


def build_body_hash(body: dict | None) -> str:
    """Stable hash of the request body used to detect fingerprint mismatches."""
    raw = json.dumps(body, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


class InMemoryIdempotencyStore:
    """Simple in-process dict store with monotonic-clock TTL. Only for DEV"""

    def __init__(self, ttl: int):
        self._ttl = ttl
        self._data: dict[str, tuple[str, float]] = {}

    def _get(self, key: str) -> str | None:
        entry = self._data.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if time.monotonic() > expires_at:
            del self._data[key]
            return None
        return value

    def _set(self, key: str, value: str, ttl: int) -> None:
        self._data[key] = (value, time.monotonic() + ttl)

    def _delete(self, key: str) -> None:
        self._data.pop(key, None)

    async def check_and_lock(self, cache_key: str, body_hash: str) -> tuple[str, dict | None, int | None]:
        """Check state and acquire lock for a new request.
        Possible returns:
          ("proceed", None, None)            -- new request; caller must call store_result or release_lock
          ("hit", body_dict, status_int)     -- cached result; return it directly
          ("conflict", None, None)           -- in-flight; caller should return 409
          ("fingerprint_mismatch", None, None) -- same key, different body; caller should return 422
        """
        value = self._get(cache_key)

        if value is None:
            self._set(cache_key, f"{_LOCK_PREFIX}{body_hash}", _LOCK_TTL_SECONDS)
            return ("proceed", None, None)

        if value.startswith(_LOCK_PREFIX):
            return ("conflict", None, None)

        if value.startswith(_DONE_PREFIX):
            data = json.loads(value[len(_DONE_PREFIX):])
            if data["body_hash"] != body_hash:
                return ("fingerprint_mismatch", None, None)
            return ("hit", data["response_body"], data["response_status"])

        return ("conflict", None, None)

    async def store_result(self, cache_key: str, body_hash: str, response_body: dict, response_status: int) -> None:
        """Overwrite the lock entry with the final response and extend TTL"""
        data = {"body_hash": body_hash, "response_body": response_body, "response_status": response_status}
        self._set(cache_key, f"{_DONE_PREFIX}{json.dumps(data)}", self._ttl)

    async def release_lock(self, cache_key: str) -> None:
        """Delete the lock"""
        value = self._get(cache_key)
        if value and value.startswith(_LOCK_PREFIX):
            self._delete(cache_key)

    async def close(self) -> None:
        pass


class RedisIdempotencyStore:
    """Redis-backed Idempotency Store"""

    def __init__(self, redis_url: str, ttl: int):
        self._client = aioredis.from_url(redis_url, decode_responses=True)
        self._ttl = ttl

    def _rkey(self, cache_key: str) -> str:
        return f"iri:idem:{cache_key}"

    async def check_and_lock(self, cache_key: str, body_hash: str) -> tuple[str, dict | None, int | None]:
        rkey = self._rkey(cache_key)
        lock_value = f"{_LOCK_PREFIX}{body_hash}"

        is_new = await self._client.set(rkey, lock_value, nx=True, ex=_LOCK_TTL_SECONDS)
        if is_new:
            return ("proceed", None, None)

        value = await self._client.get(rkey)
        if value is None:
            is_new2 = await self._client.set(rkey, lock_value, nx=True, ex=_LOCK_TTL_SECONDS)
            if is_new2:
                return ("proceed", None, None)
            return ("conflict", None, None)

        if value.startswith(_LOCK_PREFIX):
            return ("conflict", None, None)

        if value.startswith(_DONE_PREFIX):
            data = json.loads(value[len(_DONE_PREFIX):])
            if data["body_hash"] != body_hash:
                return ("fingerprint_mismatch", None, None)
            return ("hit", data["response_body"], data["response_status"])

        return ("conflict", None, None)

    async def store_result(self, cache_key: str, body_hash: str, response_body: dict, response_status: int) -> None:
        data = {"body_hash": body_hash, "response_body": response_body, "response_status": response_status}
        await self._client.set(self._rkey(cache_key), f"{_DONE_PREFIX}{json.dumps(data)}", ex=self._ttl)

    async def release_lock(self, cache_key: str) -> None:
        rkey = self._rkey(cache_key)
        value = await self._client.get(rkey)
        if value and value.startswith(_LOCK_PREFIX):
            await self._client.delete(rkey)

    async def close(self) -> None:
        await self._client.aclose()


def create_store(redis_url: str, ttl: int) -> InMemoryIdempotencyStore | RedisIdempotencyStore:
    """Return Redis-backed store if REDIS_URL is set, in-memory otherwise."""
    if redis_url:
        store = RedisIdempotencyStore(redis_url, ttl)
        log.info("Idempotency store: Redis at %s (TTL %ds)", redis_url, ttl)
        return store
    log.info("Idempotency store: in-memory (single-instance; TTL %ds)", ttl)
    return InMemoryIdempotencyStore(ttl)
