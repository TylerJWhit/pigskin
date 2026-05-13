# ADR-011: Production Database and Cache Infrastructure (PostgreSQL + Redis)

**Status:** Accepted
**Date:** 2026-05-12
**Author:** Orchestrator Agent (Architecture Review + Blind Proposal synthesis)
**Reviewer:** Architecture Agent
**Deciders:** Engineering team
**Supersedes:** None
**Related:** ADR-001 (repo structure), ADR-002 (API design), ADR-004 (lab data store), ADR-003 (promotion pipeline)
**Issues:** #361 (ARCH-003), #362 (ARCH-006), #363 (ARCH-007)

---

## Context

ADR-004 specifies SQLite for the lab results database (`lab/results_db/`). This is appropriate for lab-local benchmark history — it is single-writer, never deployed to production users, and does not need concurrency.

However, no ADR currently specifies the **production database** for the `app/` package. The production API (`api/`) has placeholder routers for draft sessions, auction state, and player data — all of which require a persistence backend. As the system grows toward multi-user draft rooms and season-long platform features, the production persistence layer must be explicitly specified.

Two findings from the 2026-05-12 architectural review triggered this ADR:

1. **ARCH-003** (placeholder routers) — implementing draft/auction state persistence requires a database decision before implementation can begin.
2. **ARCH-010** (async boundary) — the production API is async (FastAPI); the persistence layer must support async I/O via an async-capable ORM or driver.
3. **Blind architecture proposal (2026-05-12)** — an independent senior architect, working only from the product brief, independently selected PostgreSQL + Redis as the production stack, citing: ACID correctness for auction state, JSON/JSONB for flexible projection fields, and Redis pub/sub as the only viable fan-out mechanism for multi-user WebSocket draft rooms.

### Why Not SQLite for Production

SQLite is the correct choice for the lab because:
- Single writer (no concurrent benchmark runs writing simultaneously)
- Never deployed to production users
- No network access needed

SQLite is **not** suitable for the production app because:
- Multiple simultaneous draft participants require concurrent read/write access
- The WebSocket draft room requires a pub/sub bus shared across API instances (horizontal scaling)
- SQLite's WAL mode supports limited concurrency but not multiple processes on separate machines
- Production deployments must handle concurrent bid submissions with transactional correctness

---

## Decision

**PostgreSQL 16+ for production application database. Redis 7+ for caching and WebSocket pub/sub fan-out.**

ADR-004 (SQLite for `lab/results_db/`) is **unchanged** — SQLite remains the correct choice for the lab.

---

## PostgreSQL — Production Database

### Rationale

- **ACID transactions**: Auction state transitions (pick submissions, bid placements) require transactional correctness. A concurrent bid submission must not result in a player being drafted twice.
- **JSONB columns**: Player projections, strategy configs, and roster settings have semi-structured schemas that benefit from `JSONB` — typed core fields as columns, flexible metadata in JSON.
- **Row-level security**: Supports per-league data isolation without application-layer filtering.
- **Async driver**: `asyncpg` provides native async PostgreSQL access; `SQLAlchemy 2.0` supports `asyncpg` as its async backend — compatible with the FastAPI async stack.
- **Operational maturity**: RDS (AWS), Cloud SQL (GCP), Supabase, Neon, and Render all offer managed PostgreSQL. Migration from local to cloud requires only a connection string change.

### Schema Placement

Production schema lives in `api/db/` (or `core/db/` after ADR-001 migration):

```
api/
└── db/
    ├── base.py          ← SQLAlchemy DeclarativeBase
    ├── session.py       ← async_sessionmaker, get_db dependency
    ├── models/
    │   ├── draft.py     ← Draft, Pick
    │   ├── player.py    ← Player, Projection
    │   ├── league.py    ← League, LeagueMember
    │   └── roster.py    ← Roster, RosterPlayer
    └── migrations/      ← Alembic migrations (separate from lab/results_db/)
```

`lab/results_db/` Alembic migrations are **not** shared with production migrations. Each has its own `alembic.ini`.

### ORM

`SQLAlchemy 2.0` with async support via `asyncpg`. Pydantic models in `api/schemas/` are the DTO layer — domain objects do NOT inherit from SQLAlchemy models.

### Minimal Production Schema

```sql
-- Draft lifecycle
drafts   (id UUID PK, league_id, format, status, config JSONB, started_at, completed_at)
picks    (id UUID PK, draft_id FK, pick_number, owner_id, player_id, price INT, picked_at)

-- Player data (synced from external sources by Celery workers)
players      (id TEXT PK, name, position, nfl_team, status, bye_week, external_ids JSONB)
projections  (id UUID PK, player_id FK, source, week, season_year, stats JSONB, fantasy_points, fetched_at)

-- League and roster
leagues        (id UUID PK, platform, external_id, league_type, scoring_format, settings JSONB, season_year)
league_members (league_id FK, user_id FK, team_name, draft_position)
```

---

## Redis — Cache and WebSocket Fan-Out

### Rationale

Redis is required for two distinct roles:

**Role 1: Application cache**
- Player projection TTL cache (1 hour): prevents external API calls on every recommendation request
- Draft state snapshots (30-second TTL): prevents database hammering from multiple live draft observers
- Strategy recommendation cache (5-minute TTL): keyed by `(draft_id, owner_id, strategy)` — recommendations don't change mid-pick

**Role 2: WebSocket pub/sub fan-out**
When the production API runs as multiple instances (horizontal scaling), a WebSocket connection to Instance A must receive events published by Instance B (e.g., a pick submission via the REST API hitting Instance B). Redis pub/sub is the standard solution: every pick write publishes to a Redis channel; every WebSocket handler subscribes to that channel and forwards to its connected clients.

This is **not** premature optimization. It is load-bearing for correctness: without Redis pub/sub, multi-instance deployments will have split-brain draft room state. The pattern must be established before multi-instance deployment, not retrofitted.

### Cache Strategy

Cache-aside pattern throughout:
1. Read cache → hit: return cached value
2. Read cache → miss: query database, write to cache, return
3. On write: invalidate affected cache keys; do not write-through (avoids stale cache on rollback)

### Implementation

- Library: `redis-py` with `asyncio` support (`redis.asyncio`)
- Connection: `redis.asyncio.ConnectionPool` (reused across requests via FastAPI lifespan)
- Pub/sub: `redis.asyncio.client.PubSub` subscriber in WebSocket handler
- Publisher: `await redis.publish(f"draft:{draft_id}", event_json)` in `DraftService.submit_pick()`

---

## Deployment Progression

| Phase | PostgreSQL | Redis |
|-------|-----------|-------|
| Phase 1 (CLI MVP) | Not needed — CLI is direct Python | Not needed |
| Phase 2 (FastAPI + Web) | Local PostgreSQL (Docker Compose) | Local Redis (Docker Compose) |
| Phase 3+ (Cloud) | RDS PostgreSQL or managed Postgres | ElastiCache Redis or Upstash |

Phase 1 does not require PostgreSQL because the CLI operates directly via Python without HTTP. PostgreSQL and Redis are introduced together in Phase 2 when the FastAPI application launches.

---

## Consequences

### Positive
- ACID correctness for all auction state transitions
- Async-native stack (`asyncpg` + `SQLAlchemy 2.0`) compatible with FastAPI event loop
- Redis pub/sub enables correct multi-instance WebSocket fan-out from day one
- Managed cloud options available with no application code changes (connection string only)
- ADR-004 (SQLite for lab) is completely unaffected

### Negative
- Adds PostgreSQL and Redis as development dependencies (mitigated by Docker Compose)
- `docker-compose.yml` must be provided for local dev (`make dev` target)
- `asyncpg` is not compatible with synchronous SQLAlchemy usage — all database access in `api/` must be async (consistent with FastAPI architecture)
- Lab code must never import from `api/db/` — lab keeps its own SQLite results store

### Non-decisions (deferred)

- **Connection pooling tuning**: Default SQLAlchemy pool settings are sufficient for Phase 2. Tune under measured load.
- **Read replicas**: Not needed until query volume justifies it. RDS makes this a config change.
- **Redis Cluster mode**: Single-node Redis is sufficient for Phase 2–3. Cluster mode when single-node becomes a bottleneck.
- **Full-text search**: Player search will use PostgreSQL `ILIKE` initially. Switch to `pg_trgm` or a dedicated search index if performance requires it.

---

## Implementation Checklist

- [ ] Add `asyncpg>=0.29`, `sqlalchemy[asyncio]>=2.0`, `redis[asyncio]>=5.0`, `alembic>=1.13` to `requirements-core.txt`
- [ ] Add `docker-compose.yml` with `postgres:16` and `redis:7-alpine` services
- [ ] Create `api/db/` package with `base.py`, `session.py`, and `models/`
- [ ] Create `api/db/migrations/` Alembic environment (separate from `lab/results_db/`)
- [ ] Add `make db-migrate`, `make db-upgrade`, `make dev` Makefile targets
- [ ] FastAPI lifespan handler initializes `asyncpg` connection pool and Redis connection pool on startup
- [ ] `.env.example` updated with `DATABASE_URL` and `REDIS_URL` placeholders
