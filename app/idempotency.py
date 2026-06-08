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

Select via REDIS_URL env var (see config.py).
"""

import hashlib
import json
import logging
import os
import time

import redis.asyncio as aioredis
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from redis.exceptions import WatchError

log = logging.getLogger(__name__)

_LOCK_PREFIX = "LOCKED:"
_DONE_PREFIX = "DONE:"
_LOCK_TTL_SECONDS = int(os.environ.get("LOCK_TTL_SECONDS", 60))


def build_cache_key(user_id: str, idempotency_key: str, endpoint: str) -> str:
    """Produce a scoped, opaque cache key from user + key + endpoint."""
    raw = f"{user_id}:{endpoint}:{idempotency_key}"
    return hashlib.sha256(raw.encode()).hexdigest()


def build_body_hash(body: dict | None) -> str:
    """Stable hash of the request body used to detect fingerprint mismatches."""
    raw = json.dumps(body, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


async def run_with_idempotency(store, cache_key: str, body_hash: str, adapter_fn) -> JSONResponse:
    """Run adapter_fn under idempotency control."""
    action, cached_body, cached_status = await store.check_and_lock(cache_key, body_hash)

    if action == "hit":
        return JSONResponse(content=cached_body, status_code=cached_status or 200, headers={"Idempotency-Key-Reply": "hit"})
    if action == "conflict":
        raise HTTPException(status_code=409, detail="A request with this Idempotency-Key is already in progress.", headers={"Retry-After": "2"})
    if action == "fingerprint_mismatch":
        raise HTTPException(status_code=422, detail="Idempotency-Key reused with a different request body.")

    try:
        result = await adapter_fn()
        body = result.model_dump(exclude_unset=True)
        await store.store_result(cache_key, body_hash, body, 200)
        return JSONResponse(content=body, status_code=200, headers={"Idempotency-Key-Reply": "miss"})
    except Exception:
        await store.release_lock(cache_key)
        raise


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
          ("proceed", None, None)              -- new request; caller must call store_result or release_lock
          ("hit", body_dict, status_int)       -- cached result; return it directly
          ("conflict", None, None)             -- in-flight; caller should return 409
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
        """Overwrite the lock entry with the final response and extend TTL.

        Single-threaded asyncio: no await between the check and set, so this is atomic.
        """
        value = self._get(cache_key)
        if value != f"{_LOCK_PREFIX}{body_hash}":
            return
        data = {"body_hash": body_hash, "response_body": response_body, "response_status": response_status}
        self._set(cache_key, f"{_DONE_PREFIX}{json.dumps(data)}", self._ttl)

    async def release_lock(self, cache_key: str) -> None:
        """Delete the lock.

        Single-threaded asyncio: no await between the check and delete, so this is atomic.
        """
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
            # Key expired between our SET NX and GET; try once more.
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
        """Write DONE only if we still own the lock, using WATCH/MULTI/EXEC optimistic locking.

        If the lock expired and another request acquired it between check_and_lock and here,
        the WATCH detects the change and the SET is skipped.
        """
        rkey = self._rkey(cache_key)
        expected_lock = f"{_LOCK_PREFIX}{body_hash}"
        data = {"body_hash": body_hash, "response_body": response_body, "response_status": response_status}
        done_value = f"{_DONE_PREFIX}{json.dumps(data)}"

        async with self._client.pipeline() as pipe:
            try:
                await pipe.watch(rkey)
                if await pipe.get(rkey) != expected_lock:
                    await pipe.reset()
                    return
                pipe.multi()
                pipe.set(rkey, done_value, ex=self._ttl)
                await pipe.execute()
            except WatchError:
                pass  # key changed between watch and execute; another request owns it now

    async def release_lock(self, cache_key: str) -> None:
        """Delete the lock only if it still holds a LOCKED: value, using WATCH/MULTI/EXEC.

        Prevents deleting a lock that expired and was re-acquired by a different request.
        """
        rkey = self._rkey(cache_key)

        async with self._client.pipeline() as pipe:
            try:
                await pipe.watch(rkey)
                current = await pipe.get(rkey)
                if not (current and current.startswith(_LOCK_PREFIX)):
                    await pipe.reset()
                    return
                pipe.multi()
                pipe.delete(rkey)
                await pipe.execute()
            except WatchError:
                pass  # key changed between watch and execute; leave it alone

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
