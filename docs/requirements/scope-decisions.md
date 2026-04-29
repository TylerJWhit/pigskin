# Scope Decisions — Sprint 4 Feature Scope

**Status:** Draft — Pending QA Review
**Author:** Product Manager Agent
**Date:** 2026-04-28
**Version:** 1.0
**Prerequisite:** Sprint 3 complete (420/420 tests passing) before any Sprint 4 work begins

---

## Critical Thinking Preamble

Before listing scope decisions, I must flag two risks in how scope is typically defined at this stage:

### Risk 1: Sprint 4 is gated — scope is conditional

ADR-001 and ADR-002 both place Sprint 4 work in an explicit migration sequence:
- Sprint 3: Stabilize core (420/420 tests)
- Sprint 4: Define DTO schemas; identify async refactor surface
- Sprint 5: Implement routes + WebSocket scaffold
- Sprint 6: Async migration

**This means Sprint 4 is a design and schema sprint, not an implementation sprint for the app API.** Any scope decision that treats Sprint 4 as "build the API" is wrong. Scope decisions below reflect this constraint.

### Risk 2: Auth scope (single-user vs. multi-user) must be resolved before Sprint 4 API work begins

ADR-002 defers the JWT question to "when the user base expands." But the issue #76 deliverables specifically ask to resolve this. The persona analysis (see `personas.md`) provides the answer:

**Phase 1: Commissioner-only (single user), API key auth is correct.**

The commissioner is the single write authority for a draft. Other participants (Casey) are read-only spectators. API key is sufficient for Phase 1. JWT is deferred to Phase 2 (multi-user bid submission). This resolves the ADR-002 open checklist item: *"Confirm auth strategy with product requirements before Sprint 4."*

---

## Sprint 4 Scope: IN

These items are in scope for Sprint 4, validated against the persona analysis and ADR roadmap.

### IN-1: Define all DTO schemas (`app/api/schemas/`)

**Persona driving this:** Alex (Commissioner), Morgan (Power User)
**Why now:** ADR-002 Sprint 4 commitment. Every API route requires request/response Pydantic models before implementation. This is design work, not code execution — it is safe to do before the async migration.

**Schemas required:**
- `DraftCreateRequest`, `DraftStateResponse`
- `NominateRequest`, `BidRequest`, `AuctionStateResponse`
- `BidRecommendationRequest`, `BidRecommendationResponse`
- `PlayerListResponse`, `PlayerDetailResponse`
- `LeagueSyncRequest`, `LeagueSyncResponse`
- `WebSocketEventEnvelope` (for WS stream)
- Error envelope (RFC 7807 Problem Details)

**Out-of-scope within this item:** Implementing the routes. Schema definition only.

**Success criterion:** All schemas defined, reviewed, and passing Pydantic validation tests. Route implementations stubbed with `501 Not Implemented`.

---

### IN-2: FastAPI application scaffold (`app/api/`)

**Persona driving this:** Dev (Platform Developer), Alex (Commissioner — dependency for Phase 1)
**Why now:** The route structure, versioning prefix, and middleware setup can be scaffolded without the async migration. FastAPI supports synchronous route handlers.

**Includes:**
- FastAPI app initialization with `/api/v1/` prefix
- Health check endpoint (`GET /api/v1/health`) — the one "real" endpoint delivered in Sprint 4
- Router file structure matching ADR-002 route table
- Middleware: request ID, structured logging, error handler
- OpenAPI schema visible at `/docs`

**Does not include:** Functional auction/draft/recommend routes (Sprint 5).

**Success criterion:** `GET /api/v1/health` returns `{ "data": { "status": "ok" }, "meta": { "version": "v1", ... } }`. All other routes return `501`.

---

### IN-3: Pydantic v2 migration of core models (issues #6, #7, #8)

**Persona driving this:** Dev (Platform Developer), all app personas transitively
**Why now:** Sprint 2/3 deferred these until 420/420. With 420/420 achieved, the precondition is met. Pydantic v2 models for `Player`, `Team`, and `DraftState` are a prerequisite for the DTO schemas (IN-1) to be sound.

**Includes:**
- Rewrite `Player` as Pydantic v2 `BaseModel` (#6)
- Add Pydantic validation to `Team` and `DraftState` (#7)
- Update `FantasyProsLoader` to return validated `Player` models (#8)

**Risk:** These are the highest-churn modules. Run full `pytest` after each change before proceeding.

**Success criterion:** 420/420 tests still pass after all three changes. No new `ValidationError` exceptions introduced.

---

### IN-4: Confirm and document auth strategy

**Persona driving this:** Alex (Commissioner), ADR-002 checklist resolution
**Why now:** ADR-002 explicitly gates Sprint 4 on this decision.

**Decision (from persona analysis):**
> **Phase 1: API key in `X-API-Key` header. Commissioner-only write access. All other participants are read-only via the same or a separate read key.**

**Includes:**
- Update ADR-002 auth section to reflect this confirmed decision
- Add API key middleware stub to the FastAPI scaffold (IN-2)
- Document the Phase 2 JWT trigger condition: *"When team owners can submit bids via the API (not just observe)"*

**Success criterion:** ADR-002 auth section marked Confirmed. API key middleware in scaffold.

---

### IN-5: `openapi.yaml` skeleton

**Persona driving this:** Morgan (Power User — will use the documented API), Dev
**Why now:** ADR-002 open checklist item. Auto-generated from FastAPI once routes are scaffolded.

**Includes:**
- Export FastAPI-generated OpenAPI spec to `docs/api/openapi.yaml`
- Add `make openapi` target to Makefile

**Success criterion:** `docs/api/openapi.yaml` exists, is valid, and reflects the current route structure.

---

## Sprint 4 Scope: OUT

These items are explicitly **not** in scope for Sprint 4, with rationale.

### OUT-1: WebSocket implementation

**Rejected for Sprint 4.**
Per ADR-002 migration path, WebSocket implementation is Sprint 5 (after sync routes are working). The WS broadcast architecture is defined (asyncio.Queue fan-out, reconnect snapshot) but building it before the sync foundation is ready adds integration complexity with no user value.

**Persona impact:** Casey (Team Owner) cannot see real-time state in Sprint 4. This is acceptable — there is no production app yet.

**Deferred to:** Sprint 5.

---

### OUT-2: Lab pipeline implementation (ADR-003)

**Rejected for Sprint 4.**
The promotion gate (`lab/promotion/gate.py`), results DB, and experiment management are Sprint 5 items. The lab structure does not exist yet (`lab/` directory is not created). Sprint 4 is not the migration sprint (ADR-001 gates migration on 420/420 passing, which is a Sprint 3 goal — Sprint 4 is the *first* sprint post-420).

**Exception:** If 420/420 is achieved with significant sprint capacity remaining, the lab directory scaffold (empty structure, `pyproject.toml` stubs) can be added as a stretch goal.

**Deferred to:** Sprint 5.

---

### OUT-3: Mono-repo migration (ADR-001 restructure)

**Rejected for Sprint 4.**
The ADR-001 migration (reorganizing flat structure into `core/`, `app/`, `lab/`) is explicitly a Sprint 5 item, gated on 420/420 tests. Sprint 4 work (IN-1 through IN-5) creates artifacts that will move into `app/` during the Sprint 5 migration — this is by design.

**Risk to flag:** Creating `app/api/` in Sprint 4 before the migration means there are two `app/` structures temporarily. The Sprint 4 FastAPI scaffold should be clearly marked as pre-migration work and moved in Sprint 5.

**Deferred to:** Sprint 5.

---

### OUT-4: Casey (Team Owner) bid-submission UI

**Rejected for Sprint 4.**
Casey needs to observe state, not submit bids programmatically. Building a multi-user bid submission UI requires JWT auth (Phase 2), WebSocket (Sprint 5), and a full front-end. None of these are Sprint 4 readiness.

**Deferred to:** Sprint 6 (Phase 2 trigger: multi-user bid submission requirement confirmed by product team).

---

### OUT-5: Strategy leaderboard / lab-to-user transparency

**Rejected until Sprint 6 discovery.**
Exposing strategy win-rate data to end users is a conceivable feature but requires: (a) a working lab pipeline, (b) a UX design decision, and (c) a product decision about whether users care. None of these are resolved.

**Deferred to:** Sprint 6 discovery backlog.

---

### OUT-6: Export/import of draft state between sessions

**Rejected for Sprint 4.**
Morgan (Power User) may want to export rosters. This requires a stable `DraftStateResponse` schema (IN-1) as a prerequisite. If IN-1 is complete, an export endpoint is a candidate for Sprint 5, not Sprint 4.

**Deferred to:** Sprint 5 (dependency: IN-1 schemas complete).

---

## Auth Decision Summary (Resolves ADR-002 Open Item)

| Phase | Mechanism | Trigger | Sprint |
|-------|-----------|---------|--------|
| Phase 1 (now) | API key — `X-API-Key` header | Commissioner-only write; app is single-user | Sprint 4 |
| Phase 2 | JWT tokens | Team owners submit bids via API (multi-user write) | Sprint 6+ |
| Phase 3 | OAuth2 (future) | If the app becomes a public SaaS | Not planned |

**Confirmed:** API key auth is sufficient for Sprint 4 and Sprint 5. The JWT question is deferred until Casey's use case requires programmatic bid submission — a decision that must be made explicitly, not implicitly absorbed into the API design.

---

## Scope Decision Matrix (RICE Sketch)

| Item | Reach | Impact | Confidence | Effort | RICE | Decision |
|------|-------|--------|------------|--------|------|----------|
| IN-1: DTO schemas | 5 | 4 | 90% | M | 18.0 | IN |
| IN-2: FastAPI scaffold + health | 5 | 3 | 95% | S | 28.5 | IN |
| IN-3: Pydantic v2 migration | 5 | 4 | 80% | M | 16.0 | IN |
| IN-4: Auth decision doc | 3 | 5 | 95% | XS | 57.0 | IN (low effort, high unblock) |
| IN-5: openapi.yaml | 3 | 2 | 90% | XS | 54.0 | IN (near-zero effort) |
| OUT-1: WebSocket | 4 | 4 | 70% | L | 1.1 | OUT (ADR-002 migration sequence) |
| OUT-2: Lab pipeline | 2 | 5 | 60% | XL | 0.3 | OUT (Sprint 5 gate) |
| OUT-3: Mono-repo migration | 5 | 5 | 75% | XL | 0.5 | OUT (Sprint 5 gate) |
| OUT-4: Casey bid UI | 2 | 3 | 50% | XL | 0.1 | OUT (Phase 2) |

*Reach = personas affected; Impact = 1–5; Effort = XS/S/M/L/XL (XS≈0.1, XL≈10)*

---

## Risks to Carry Forward

| Risk | Likelihood | Impact | Owner | Mitigation |
|------|-----------|--------|-------|------------|
| Pydantic v2 migration (IN-3) breaks tests | High | High | Backend Agent | Run full pytest after each model; fix before moving to next |
| FastAPI scaffold creates `app/` structure that conflicts with Sprint 5 migration | Medium | Medium | Architecture Agent | Pre-agree naming convention for pre-migration `app/` artifacts |
| Auth decision (IN-4) is reviewed by Security Agent before Sprint 4 build begins | Medium | High | PM Agent | Flag ADR-002 update for Security Agent sign-off |
| Sprint 3 not complete when Sprint 4 begins | Low | High | Project Manager | Hard gate: do not begin IN-1 until 420/420 confirmed |

---

## Summary

**Sprint 4 is a design + schema + scaffold sprint, not a working API sprint.**

The three most important decisions made here:
1. **API key auth is confirmed for Phase 1** — JWT is deferred to Phase 2 (team owner bid submission)
2. **WebSocket is out of scope for Sprint 4** — per ADR-002 migration sequence
3. **Lab pipeline and mono-repo migration are Sprint 5 gates** — conditional on 420/420

These decisions unblock Sprint 4 API schema work (IN-1) and resolve the outstanding ADR-002 checklist item on auth strategy.
