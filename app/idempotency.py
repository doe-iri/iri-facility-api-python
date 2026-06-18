"""Idempotency store for mutating API endpoints (submit_job, update_job).

Behaviour by Idempotency-Key header:
  - No header         -> pass through, normal execution every time.
  - First request     -> lock key, run handler, cache 200 response, return it.
  - Retry same key    -> return cached response without calling the adapter again.
  - In-flight same key -> 409 Conflict (Retry-After: 2).
  - Same key, different body -> 422 Unprocessable Entity.
  - Adapter raises    -> lock is released; client may retry safely.

The backing store is defined via IRI_IDEMPOTENCY_STORE (see create_store).
Reference implementations:
  - InMemoryIdempotencyStore  : in-process dict; dev/single-instance only.
  - RedisIdempotencyStore     : Redis-backed;
"""

import hashlib
import importlib
import json
import logging
import os
from abc import ABC, abstractmethod
from enum import Enum

from fastapi import HTTPException
from fastapi.responses import JSONResponse

log = logging.getLogger(__name__)


class LockState(str, Enum):
    LOCKED = "LOCKED"
    DONE = "DONE"


def build_cache_key(user_id: str, idempotency_key: str, endpoint: str) -> str:
    """Produce a scoped, opaque cache key from user + key + endpoint."""
    raw = f"{user_id}:{endpoint}:{idempotency_key}"
    return hashlib.sha256(raw.encode()).hexdigest()


def build_body_hash(body: dict | None) -> str:
    """Stable hash of the request body used to detect fingerprint mismatches."""
    raw = json.dumps(body, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


class IdempotencyStore(ABC):
    """Abstract class for idempotency backing stores.
    """

    @abstractmethod
    async def check_and_lock(self, cache_key: str, body_hash: str) -> tuple[str, dict | None, int | None]:
        """Check state and acquire lock for a new request.

        Returns one of:
          ("proceed", None, None)              -- new request; caller must call store_result or release_lock
          ("hit", body_dict, status_int)       -- cached result; return it directly
          ("conflict", None, None)             -- in-flight; caller should return 409
          ("fingerprint_mismatch", None, None) -- same key, different body; caller should return 422
        """

    @abstractmethod
    async def store_result(self, cache_key: str, body_hash: str, response_body: dict, response_status: int) -> None:
        """Persist the final response and transition the key to DONE state.
        Must be owner-checked: no-op if this caller no longer holds the lock.
        """

    @abstractmethod
    async def delete_lock(self, cache_key: str) -> None:
        """Delete the lock entry when the adapter raises an exception.
        Must be owner-checked: no-op if the key is no longer in LOCKED state.
        """

    @abstractmethod
    async def close(self) -> None:
        """Release connections and resources at application shutdown."""


async def run_with_idempotency(store: IdempotencyStore, cache_key: str, body_hash: str, adapter_fn) -> JSONResponse:
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
    except Exception as exc:
        log.error("Adapter raised during idempotent call; releasing lock for key %s: %s", cache_key, exc)
        await store.delete_lock(cache_key)
        raise


def create_store() -> IdempotencyStore:
    """Return the idempotency store configured via IRI_IDEMPOTENCY_STORE.

    The named class is imported and instantiated with no arguments — it reads any
    connection strings or config it needs from env vars.
    Defaults to app.demo_adapter.InMemoryIdempotencyStore (single-instance; not for production).
    """
    class_path = os.environ.get("IRI_IDEMPOTENCY_STORE", "app.demo_adapter.InMemoryIdempotencyStore")
    parts = class_path.rsplit(".", 1)
    module = importlib.import_module(parts[0])
    StoreClass = getattr(module, parts[1])
    if not issubclass(StoreClass, IdempotencyStore):
        raise ValueError(f"{class_path} must subclass IdempotencyStore")
    store = StoreClass()
    log.info("Idempotency store: %s", class_path)
    return store
