# S3DF Filesystem Adapter — Design Doc

## Context

The `iri-facility-api-python` project exposes a uniform REST contract for interacting with DOE compute facilities. It ships with a reference (`DemoAdapter`) implementation that runs in a single process with an in-memory task store — adequate for demos, insufficient for production. This document defines how the S3DF filesystem adapter should be built out as a production service, how it integrates with the IRI spec's task model, and why Redis is the right queue backend for our deployment.

Scope is bounded: small/medium file operations (download, upload, compress, cp/mv) over POSIX-mounted S3DF storage. Large-scale cross-site transfers (Globus) are explicitly out of scope.

---

## IRI Filesystem Design Pattern

Two patterns compose the framework:

### 1. Adapter Pattern (structural)

Each router (`filesystem`, `task`, `status`, `account`, `compute`) defines an **abstract `FacilityAdapter`**. Concrete adapters are loaded at startup via env vars (`IRI_API_ADAPTER_{router}`). The router never talks to storage directly — it marshals HTTP into method calls on the adapter, which owns all facility-specific business logic.

This means the REST surface is fixed by the IRI spec, while the *implementation* behind each method is fully facility-owned. For S3DF, that implementation is POSIX syscalls and `sudo -u <user>` subprocess invocations against `/sdf/`.

### 2. Command + Task Queue Pattern (behavioral)

Every filesystem operation — even fast ones like `download` — is wrapped as a `TaskCommand{router, command, args}` and submitted to a task queue. Results are returned as `Task{id, status, result}` records.

This gives the framework three guarantees for free:
- **Uniform error handling** — every failure becomes `TaskStatus.failed` with an error payload
- **Uniform polling surface** — clients always poll `GET /task/{id}`, regardless of operation
- **Auditability** — every operation has a persisted record keyed by `task_id`

Fast ops (`download`, `upload`) are executed inline: the router enqueues, waits, and returns the result in the same HTTP response. Slow ops (`compress`, `extract`) return `task_id` immediately; the client polls.

---

## Target Architecture

The S3DF filesystem adapter is extracted from the IRI API process into a **separate worker microservice**. Redis is the sole integration surface between them.

```
┌──────────────────────┐        ┌──────────────────────┐        ┌──────────────────────┐
│    IRI API           │        │       Redis          │        │  Filesystem Worker   │
│    (FastAPI)         │◄──────►│   (task store +      │◄──────►│   (s3df adapter)     │
│  stateless, scales   │        │    work queue)       │        │  owns /sdf/ mount    │
│  horizontally        │        │                      │        │  runs sudo -u <user> │
└──────────────────────┘        └──────────────────────┘        └──────────────────────┘
         ▲                                                                  │
         │ HTTPS                                                            │ POSIX
         │                                                                  ▼
┌──────────────────────┐                                         ┌──────────────────────┐
│       Client         │                                         │   Weka / s3df        │
│                      │                                         │                      │
└──────────────────────┘                                         └──────────────────────┘
```

**Why two services, not one:**

- The IRI API is stateless HTTP and scales horizontally behind a load balancer. It needs no filesystem mount.
- The Filesystem Worker must run on hosts with `/sdf/` mounted and `sudo` policy configured. That's a very different deployment profile.
- Decoupling lets each scale on its own axis (API by request volume, workers by I/O volume).
- The IRI API can be upgraded independently of the S3DF implementation.

---

## Task Queue: Why Redis

### Brief comparison

| Option | Model | Fit for our problem |
|---|---|---|
| **In-process dict** | Module-level state | Fails across gunicorn workers; no persistence; dev-only |
| **Celery + Redis/RabbitMQ** | Full distributed task framework | Overkill — we don't need scheduled tasks, chord/group primitives, or cross-host worker pools |
| **arq** (async Redis queue) | Lightweight async Python queue | Good fit, but `on_task` is blocking subprocess code — asyncio advantages are wasted |
| **Redis + ThreadPoolExecutor** | Redis for state/queue, workers pull blocking jobs | Matches our workload shape directly |

### Problem context — why Redis fits

Our workload has a specific shape that makes Redis the right primitive:

1. **Tasks are short and blocking.** They are subprocess calls to `tar`, `cat`, `cp` — not long-running Python functions that benefit from an async task framework. Anything with a richer execution model than "run this subprocess and record the result" is overhead we don't need.

2. **State is the hard part, not execution.** The IRI spec's task interface (`put_task`, `get_task`, `on_task`) is essentially three operations: write a record, read a record, pop a queue. Redis does all three natively with `HSET`, `HGETALL`, and `BLPOP`. Celery would wrap these same primitives in a much larger abstraction.

3. **Multi-worker coordination is the only real requirement.** Gunicorn forks multiple workers; any of them might serve the `GET /task/{id}` poll for a task another worker enqueued. Redis gives us shared state with atomic operations and built-in TTL for task record cleanup.

4. **Operational simplicity matters.** Redis is a single container dependency, already well-understood, and already likely present in the S3DF stack. Celery adds a broker + worker process + config + monitoring surface — all for primitives Redis provides directly.

5. **Workers run where `/sdf/` is mounted.** We don't need cross-host worker distribution (Celery's selling point). All workers run on storage-adjacent hosts sharing the same mount.

**Decision: Redis as both task store (hashes keyed by `task:{id}`) and work queue (list `tasks:queue`). Worker processes pull with `BLPOP`, execute `on_task()` on a `ThreadPoolExecutor`, and write results back with `HSET`.**

---

## Sequence of Interactions

```
┌──────────┐      ┌─────────────────────┐      ┌───────────┐      ┌──────────────────────┐
│  Client  │      │   IRI API (FastAPI)  │      │   Redis   │      │  Filesystem Worker   │
│          │      │                      │      │           │      │   (s3df adapter)     │
└────┬─────┘      └──────────┬──────────┘      └─────┬─────┘      └──────────┬───────────┘
     │                       │                        │                        │
     │ POST /filesystem/      │                        │                        │
     │ compress/{resource_id} │                        │                        │
     │──────────────────────►│                        │                        │
     │                       │ HSET task:{id}          │                        │
     │                       │ status=pending          │                        │
     │                       │ command=TaskCommand{...}│                        │
     │                       │ LPUSH tasks:queue {id} │                        │
     │                       │───────────────────────►│                        │
     │  {task_id, "pending"} │                        │                        │
     │◄──────────────────────│                        │                        │
     │                       │                        │                        │
     │                       │                        │ BLPOP tasks:queue      │
     │                       │                        │◄───────────────────────│
     │                       │                        │ → task_id              │
     │                       │                        │───────────────────────►│
     │                       │                        │                        │ HSET status=active
     │                       │                        │◄───────────────────────│
     │                       │                        │                        │
     │                       │                        │                        │ on_task()
     │                       │                        │                        │ validate_path()
     │                       │                        │                        │ sudo -u <user> tar
     │                       │                        │                        │ → /sdf/scratch/...
     │                       │                        │                        │
     │                       │                        │ HSET status=completed  │
     │                       │                        │ result={target_path}   │
     │                       │                        │◄───────────────────────│
     │                       │                        │                        │
     │ GET /task/{task_id}   │                        │                        │
     │──────────────────────►│ HGETALL task:{id}      │                        │
     │                       │───────────────────────►│                        │
     │                       │◄───────────────────────│                        │
     │ {status, result}      │                        │                        │
     │◄──────────────────────│                        │                        │
```

**Three integration points, all through Redis:**

| Interface method | Redis operation |
|---|---|
| `put_task(cmd) → task_id` | `HSET task:{id} ...` + `LPUSH tasks:queue {id}` |
| `get_task(id) → Task` | `HGETALL task:{id}` |
| `on_task()` dispatch | Worker `BLPOP tasks:queue` + write-back via `HSET` |

The IRI API and Filesystem Worker **never communicate directly**. The worker owns `/sdf/` access and `sudo` impersonation; the API owns request/response and auth. Redis is the only shared state.

---

## Key Design Decisions

1. **Execution identity — `sudo -u <username>`.** Files on `/sdf/` have real UNIX ownership. The worker service account must impersonate the authenticated user per operation. Requires a scoped sudoers policy. Do not use `os.setuid()` — it's incompatible with async runtimes.

2. **Path validation is a security boundary.** Every path arg is resolved via `os.path.realpath()` and checked against an allowlist (`/sdf/home`, `/sdf/data`, `/sdf/group`, `/sdf/scratch`) *after* resolution, to defeat symlink escapes.

3. **Size checks belong at the router layer.** The 5 MB `OPS_SIZE_LIMIT` is enforced before the task is enqueued for uploads; download must re-check via `stat()` in the adapter before reading, to avoid loading a large file just to reject it.

4. **Task records have TTL.** Redis keys use `EXPIRE` (e.g. 24h) so completed tasks are garbage-collected. Anything needing long-term audit belongs in a separate log.

5. **Ceph S3 presigned URLs are out of scope.** The current IRI spec is sufficient for small/medium files. Presigned URLs are an optional non-spec extension, feature-flagged, and only worth adding if users routinely hit the 5 MB ceiling *and* the files are already in Ceph (not Weka).

---

## Verification

- **Unit:** Mock Redis; assert `put_task`/`get_task`/`on_task` write and read correct keys.
- **Integration:** Run IRI API + Worker + Redis in docker-compose; upload < 5 MB file, download it back, assert byte-identical.
- **Security:** Attempt path traversal (`../../etc/passwd`) → expect `400`. Attempt upload > 5 MB → expect `413`.
- **Async:** Submit `compress` on a directory, poll `/task/{id}` until `completed`, verify tar exists at the target path on `/sdf/`.
- **Multi-worker:** Run 2+ gunicorn workers and 2+ Filesystem Workers; verify a task enqueued by any API worker is picked up by any filesystem worker and visible to any API worker on poll.