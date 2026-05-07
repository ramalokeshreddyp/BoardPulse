# Questionnaire — BoardPulse (Real-Time Task Board)

Date: 2026-05-07

## 1) Redis vs In‑Memory Channel Layer

- Scalability: In‑memory works only for a single process — suitable for local development. Redis supports multiple processes and machines, enabling horizontal scaling of ASGI workers.
- Multi‑process support: Redis is required when you have more than one worker/process; in‑memory cannot broadcast across processes.
- Single point of failure: Redis is an external dependency and can be a SPOF. Mitigate with Redis HA (replication, Sentinel/Cluster) and monitoring. In‑memory avoids external ops but sacrifices real scaling.
- Network latency: Redis adds a small network hop for each group_send/group_receive; this is usually acceptable. In‑memory has virtually zero overhead but is limited to single process.
- Trade‑offs: Redis requires ops and capacity planning but enables production readiness and horizontal scalability; in‑memory is simpler but not production‑grade for multi‑instance deployments.

## 2) Biggest async challenge & `database_sync_to_async`

- Challenge: Preventing accidental blocking calls inside the consumer (synchronous DB calls, `time.sleep`, heavy CPU) which freeze the event loop and stall all connections on that worker.
- `database_sync_to_async`: wraps synchronous ORM/db calls and executes them in a thread from a threadpool so the async event loop is not blocked; you `await` the wrapper in your consumer.
- Performance implications: thread context switching and threadpool contention add latency and CPU cost. Under heavy load threadpool exhaustion can limit throughput. Mitigations: minimize sync work per message, use efficient queries, tune pool size, and move heavy work to async drivers or background workers.

## 3) Event loop & blocking calls (brief)

- Event loop: a single thread (per worker) scheduling coroutines and awaiting I/O; it yields control while waiting so other tasks can run.
- Blocking calls (synchronous I/O or CPU work) stop the loop, preventing it from scheduling other coroutines — this causes global latency spikes and stalls WebSocket handling.

## 4) Scaling to thousands of concurrent connections per board

- Horizontal ASGI scaling: run many Daphne/Uvicorn instances behind a WebSocket‑capable load balancer (no proxies that drop Upgrade). Redis channel layer provides cross‑process pub/sub so sticky sessions are unnecessary.
- Partitioning/sharding: if a single board has huge fan‑out, shard by board ID (route hot boards to dedicated pools) or limit per‑board fan‑out via logical partitions.
- DB scaling: use read replicas for reads, move non‑critical writes to background jobs, and keep per‑message DB work minimal. Indexes and efficient queries are critical.
- Caching: cache board metadata and lists in Redis to avoid DB roundtrips on connect or presence updates; use TTLs and invalidate on writes.
- Broadcast optimizations: reduce payload size, aggregate messages, use binary/compact formats, and avoid broadcasting unchanged state.
- Connection management: enforce limits, use autoscaling, apply backpressure, and gracefully drain connections during deploys.

## 5) Security implications of long‑lived WebSockets

- Session lifetime: WebSocket uses the initial HTTP handshake for auth (cookies/tokens). A stolen cookie can grant long‑lived access — use TLS (wss), `HttpOnly`/`Secure` cookies, short session TTLs, and reauthorization for sensitive actions.
- Session hijacking & revocation: provide server‑side revocation and a mechanism to close sockets when sessions are invalidated (e.g., a revocation set checked periodically or broadcast control messages to clients).
- Token expiry & refresh: consider short‑lived access tokens + refresh flow, or revalidate the session periodically on the socket (e.g., check session validity every N minutes).
- Per‑message authorization: validate that the acting user can perform the action (task belongs to board, user permissions) — never trust client input.
- Rate limiting & abuse: apply per‑connection and per‑user rate limits, idle timeouts, and monitoring to detect abuse.

## 6) Automated testing strategy for the consumer

- Unit tests:
  - Test consumer helper functions and small synchronous parts (serialization, validation). Mock DB calls to exercise logic.
- Integration tests (Channels utilities):
  - Use `channels.testing.WebsocketCommunicator` to test connect/disconnect behavior (authenticated accept, unauthenticated close with 4001).
  - Spin up multiple communicators to assert broadcasting: send `move_task` from one instance and assert others receive `task.moved` and DB was updated.
- End‑to‑end tests:
  - Start the full stack (Daphne, Redis, Postgres) in CI/staging and use real WebSocket clients to verify auth handshake, presence, move broadcasts, and persistence.
- Concurrency/race tests:
  - Simulate simultaneous `move_task` messages and verify consistent final state; add tests for idempotency and locking if required.
- Security & regression tests:
  - Verify unauthorized actions are rejected, sessions expire and revoke sockets, and malformed messages don't crash the consumer.
- Load/perf tests:
  - Use `scripts/benchmark.py` in staging to measure connection success, broadcast latency, and tail‑latency under realistic concurrency.

---

If you want, I can also add a short `tests/` scaffold demonstrating `WebsocketCommunicator` usage.
