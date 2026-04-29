# ADR-002: Public REST API Design (FastAPI, Versioned, HTTP-only UI)

**Status:** Revised and Accepted
**Date:** 2026-04-28
**Revised:** 2026-04-28
**Author:** Architecture Agent (via Orchestrator)
**Reviewer:** Architecture Agent
**Deciders:** Engineering team

---

## Context

The production app (`app/`) requires a documented, publicly accessible API. Currently, all business logic is exposed only via the CLI (`cli/`) or as direct Python imports. There is no HTTP interface.

Existing GitHub issues already acknowledge this direction:
- Issue #11 — Scaffold FastAPI application with router structure
- Issue #12 — Replace threading.Timer with asyncio
- Issue #13 — Add FastAPI WebSocket endpoint for real-time auction
- Issue #14 — Convert SleeperAPI from requests to httpx async client

The web UI must consume the API exclusively via HTTP — no direct Python imports across the boundary.

### Options Considered

| Option | Pros | Cons |
|--------|------|------|
| Flask (sync) | Already referenced in architecture notes | Sync-only; auction real-time state requires WebSocket; blocking I/O |
| **FastAPI (async)** | Async-native; automatic OpenAPI docs; Pydantic validation built-in; WebSocket support; issues #11–14 already target it | New dependency; team must learn async patterns |
| GraphQL (Strawberry/Ariadne) | Flexible queries; single endpoint | Over-engineered for this use case; no real-time subscription need that WebSocket doesn't cover more simply |

### Real-time State Requirement

The live draft view needs sub-second bid updates. Options:
- **WebSocket** (issue #13): Persistent connection, server pushes state deltas. Fits auction perfectly.
- Server-Sent Events (SSE): One-way, simpler, but no bidirectional communication.
- Long-polling: Worst latency; only fallback.

**Decision: WebSocket for live auction state, REST for everything else.**

---

## Decision

**FastAPI with versioned REST routes + WebSocket for real-time auction state.**

### Route Structure

```
/api/v1/
├── /health                    GET   → service health
├── /draft/
│   ├── /                      POST  → create draft session
│   ├── /{draft_id}            GET   → get draft state
│   ├── /{draft_id}            DELETE → end draft session
│   └── /{draft_id}/sync       POST  → sync from Sleeper (if draft_id provided)
├── /auction/
│   ├── /{draft_id}/nominate   POST  → nominate player
│   ├── /{draft_id}/bid        POST  → place bid
│   └── /{draft_id}/state      GET   → current auction state snapshot
├── /recommend/
│   └── /bid                   POST  → get bid recommendation for player + context
├── /players/
│   ├── /                      GET   → player list (paginated, filterable)
│   └── /{player_id}           GET   → player detail
├── /league/
│   └── /sync/{sleeper_league_id}  POST → import league from Sleeper
└── /ws/
    └── /{draft_id}            WS    → real-time auction state stream
```

### Versioning Policy
- All routes prefixed with `/api/v1/`
- Breaking changes require a new version prefix (`/api/v2/`)
- Deprecation period: one full season (minimum) before removing a version
- Version is declared in `app/api/__init__.py` and reflected in OpenAPI spec

### Response Contract
- All responses use a consistent envelope:
  ```json
  { "data": {...}, "meta": {"version": "v1", "timestamp": "..."} }
  ```
- Errors use RFC 7807 Problem Details format
- No domain objects cross the API boundary — request/response DTOs only (Pydantic models in `app/api/schemas/`)

### Authentication
- Phase 1: API key in `X-API-Key` header (simple, sufficient for single-user/commissioner use)
- Phase 2: JWT for multi-user/multi-team scenarios (deferred; requires user model)

---

## Consequences

### Positive
- Auto-generated OpenAPI docs at `/docs` (Swagger UI) and `/redoc` — satisfies the "publicly documented API" goal
- Pydantic validation at the boundary — no malformed data reaches domain objects
- WebSocket eliminates polling for live draft state
- Issues #11–14 are already scoped to this direction; no wasted work

### Negative
- Async requires refactoring `classes/auction.py` threading model (issue #12) — this is a Sprint 4/5 item
- API key auth is not sufficient for a public multi-tenant SaaS product; deferred JWT work will be required if the user base expands
- `SleeperDraftService` and `BidRecommendationService` must be wrapped behind DTO schemas — cannot be called directly from routes

### Migration Path
1. Sprint 3: No changes — stabilize core
2. Sprint 4: Define all DTO schemas; identify all services needing async refactor
3. Sprint 5: Implement `/api/v1/` routes with sync wrappers (FastAPI supports sync routes); WebSocket scaffold
4. Sprint 6: Async migration for auction state; WebSocket live state

---

## Review Checklist (Resolved)
- [ ] Draft `app/api/schemas/` with all request/response Pydantic models
- [ ] Create `docs/api/openapi.yaml` skeleton
- [ ] Confirm auth strategy with product requirements before Sprint 4
- [ ] Validate WebSocket message format with Frontend Agent

---

## Critical Thinking Review (Architecture Agent — 2026-04-28)

### Thread Safety: The Central Revision

**This is the reason this ADR needed revision.** Three threading bugs were fixed in Sprints 2–3. The original ADR delegates thread safety to issue #12 without specifying the migration contract. That gap is closed here.

#### Current threading model in `classes/auction.py` (verified by code inspection)

```
threading.RLock()          → self._lock  (guards all shared state mutations)
threading.Timer(1.0, ...)  → 5 instances for nomination + bid tick callbacks
```

The existing pattern is: timers are started outside `self._lock`, but state mutations inside the tick callbacks acquire `self._lock`. This is correct for the threading model, but means the asyncio migration must preserve the same invariant.

#### Thread Safety Migration Contract (issue #12)

**The rule**: Do NOT mix `threading.Timer` with the asyncio event loop. The transition must be atomic — either everything stays on threads, or everything moves to asyncio. Partial migration is the most dangerous state.

**Migration sequence (mandatory order):**

1. **Phase 1 (sync wrappers first)**: FastAPI supports synchronous route handlers. Implement all REST routes using `def` (not `async def`) calling the existing sync auction engine directly. No asyncio in the domain layer yet. This is safe immediately.

2. **Phase 2 (asyncio migration, issue #12)**: Refactor `Auction` class to use `asyncio.Task` for timers and `asyncio.Lock` for state guards:
   - Replace `threading.RLock()` → `asyncio.Lock()`
   - Replace `threading.Timer(1.0, tick_fn)` → `asyncio.create_task(asyncio.sleep(1.0)); tick_fn()` via `asyncio.get_event_loop().call_later(1.0, tick_fn)` (**preferred**) or a task wrapper
   - All callbacks must be coroutines (`async def`) or scheduled via `loop.call_soon_threadsafe()` if called from a non-async context
   - `asyncio.get_running_loop()` (not the deprecated `asyncio.get_event_loop()`) must be used everywhere

3. **Phase 3 (WebSocket, issue #13)**: WebSocket endpoint is only implemented AFTER Phase 2 is complete. Do not implement WebSocket against the sync/threading auction engine — the GIL plus asyncio event loop create undetectable race conditions.

**Invariant**: `asyncio.Lock` is not reentrant. The current `threading.RLock` IS reentrant (used in `nominate_player` which is called from `place_bid` callback paths). The asyncio migration must audit all call paths for recursive lock acquisition and break cycles.

#### WebSocket State Broadcast Architecture

The original ADR specifies the WebSocket endpoint but not how state is delivered to multiple connected clients. This must be explicit to avoid reimplementation bugs:

```
Pattern: asyncio.Queue per connection (fan-out broadcast)

AuctionEngine (produces events)
    │
    ▼
ConnectionManager
    ├── asyncio.Queue → WebSocket connection 1 (viewer 1)
    ├── asyncio.Queue → WebSocket connection 2 (viewer 2)
    └── asyncio.Queue → WebSocket connection N (mobile client)

Each connection has a dedicated coroutine: async for msg in queue: await ws.send_json(msg)
```

- State delta format (minimum required fields):
  ```json
  {
    "event": "bid_placed | player_nominated | timer_tick | auction_complete",
    "draft_id": "<id>",
    "payload": { ... event-specific data ... },
    "timestamp": "ISO-8601"
  }
  ```
- `ConnectionManager` is a singleton per draft session (not per FastAPI app instance)
- On client reconnect: immediately send full state snapshot, then switch to delta stream

### Assumptions Examined

1. **"WebSocket is the right real-time primitive"** — Correct for this use case. The auction is event-driven (bids arrive sporadically, timer ticks are regular). SSE would work for read-only viewers but precludes future bidirectional use (e.g., mobile bidding client).

2. **"API key auth is sufficient for Phase 1"** — True for a single-commissioner use case. Flag: storing an API key in a request header means it appears in server logs. Ensure FastAPI middleware strips `X-API-Key` from access logs before any deployment.

3. **"Sprint 5 is safe for WebSocket implementation"** — Only safe if Phase 2 (asyncio migration) is complete. If Sprint 5 scope includes both the asyncio refactor AND the WebSocket endpoint, they must be sequenced within the sprint, not parallelized.

### Risks

- **Recursive lock on asyncio.Lock**: `asyncio.Lock` is NOT reentrant. Current code uses `threading.RLock` (reentrant). Audit required before Phase 2.
- **Event loop lifecycle**: FastAPI uses its own event loop. The `Auction` instance must live inside that loop — it cannot be created in a different thread and passed to the loop.
- **`SleeperDraftService` uses `requests` (sync)**: Must be wrapped with `asyncio.to_thread()` or converted to `httpx` (issue #14) before being called from async routes. Do not block the event loop with sync I/O.
- **API key in logs**: Log sanitization required before any deployment.

### Migration Timeline Revision

| Sprint | Deliverable | Constraint |
|--------|-------------|------------|
| 4 | DTO schemas + route stubs (sync) | Safe now |
| 5 (early) | asyncio migration of `Auction` (issue #12) + httpx for SleeperAPI (issue #14) | Must complete before WebSocket |
| 5 (late) | WebSocket endpoint (issue #13) | Requires Phase 2 complete |
| 6 | Live testing + monitoring | |
