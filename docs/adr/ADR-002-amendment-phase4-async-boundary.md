# ADR-002 Amendment: Phase 4 Async Adapter Boundary Review
**Date:** 2026-05-01  
**Author:** Architecture Agent (Sprint 7, C0 gate)  
**Status:** Accepted  
**Amends:** ADR-002 (API Design)

---

## Context

Sprint 7 Track C required an Architecture Agent review before `#12` (asyncio Timer) and `#14` (httpx) implementation began. The sprint plan stated: *"Does `Auction` stay synchronous and get an async wrapper, or does the class itself become async? How does `asyncio.create_task()` integrate with the existing CLI flow?"*

Since the sprint plan was written, the **sealed-bid refactor** (PR merged in Sprint 7) rewrote `classes/auction.py` entirely, eliminating `threading.Timer`, `threading.RLock`, and all bid-countdown logic. This materially changes the Phase 4 scope.

---

## Findings

### 1. #12 Is Already Resolved

`#12` ("Replace threading.Timer auction countdown with asyncio") had three acceptance criteria:

| Criterion | Status |
|-----------|--------|
| No `threading.Timer` in auction code | ✅ Resolved by sealed-bid refactor |
| Bid countdown works correctly end-to-end in tests | ✅ Sealed-bid model has no countdown; `nominate_player()` resolves synchronously |
| Timer cancellation works when a new bid is placed | ✅ N/A — sealed-bid model has no outstanding timers to cancel |

**Decision: Close `#12` as resolved by the sealed-bid refactor. No implementation needed.**

### 2. `Auction` Stays Synchronous

The `Auction` class orchestrates a complete sealed-bid draft via `start_auction()` → `draft.run_complete_draft()`. This is a CPU-bound, synchronous workflow. Converting it to `async def` would require:

- Every strategy's `calculate_bid()` to become async (cascading refactor across 18+ strategy classes)
- Every caller (CLI, simulation, lab benchmarks) to await the call
- No meaningful benefit — the work is in-process computation, not I/O

**Decision: `Auction` remains synchronous.** FastAPI endpoint handlers that call `Auction.start_auction()` MUST use `asyncio.run_in_executor(None, auction.start_auction)` to avoid blocking the event loop thread.

### 3. FastAPI Adapter Pattern

```python
# api/routers/draft.py — correct pattern
import asyncio
from fastapi import APIRouter
from classes.auction import Auction

router = APIRouter()

@router.post("/drafts/{draft_id}/start")
async def start_draft(draft_id: str):
    auction = ...  # build from draft state
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, auction.start_auction)
    return {"status": "complete"}
```

This is the only place an async boundary is needed. The `Auction`, `Draft`, `Team`, and `Strategy` objects are not async.

### 4. CLI Path Unaffected

```python
# cli/commands.py — existing pattern, no change needed
auction = Auction(draft)
auction.start_auction()  # synchronous, fine in CLI context
```

### 5. `#14` Is the Remaining Phase 4 Work

`api/sleeper_api.py` uses `requests.Session` with `time.sleep()` for rate limiting. This blocks the event loop when called from an async FastAPI handler. Converting it to `httpx.AsyncClient` is the actual remaining Phase 4 work.

**Migration scope for `#14`:**
- Replace `import requests` → `import httpx`
- `_make_request()` becomes `async def _make_request()` using `httpx.AsyncClient`
- Rate limiting: `time.sleep()` → `await asyncio.sleep()`
- All public methods (`get_draft`, `get_picks`, `get_all_players`, etc.) become `async def`
- All callers in `services/sleeper_draft_service.py` must be updated to `await`
- Add `httpx>=0.27.0` to `requirements-core.txt`

**Backward compatibility:** `services/bid_recommendation_service.py` currently calls `self.sleeper_api.get_draft(draft_id)` synchronously inside `_get_sleeper_draft_context()`. After #14, this method must also become async, or the `BidRecommendationService` must accept an optional injected `httpx.AsyncClient`.

---

## Decisions

| # | Decision |
|---|----------|
| 1 | Close `#12` as resolved — threading.Timer is already gone |
| 2 | `Auction` stays synchronous; FastAPI uses `run_in_executor` adapter |
| 3 | `#14` proceeds: `SleeperAPI` → `httpx.AsyncClient`; `time.sleep` → `asyncio.sleep` |
| 4 | `BidRecommendationService._get_sleeper_draft_context()` must become async in same PR as `#14` |
| 5 | `httpx>=0.27.0` added to `requirements-core.txt` |
| 6 | No async decorator needed on strategy classes; strategies stay synchronous |

---

## Implementation Checklist for `#14`

- [ ] `pip install httpx` + add to `requirements-core.txt`
- [ ] Rewrite `api/sleeper_api.py`: all methods async, `httpx.AsyncClient`, `asyncio.sleep`
- [ ] Update `services/sleeper_draft_service.py`: await all SleeperAPI calls
- [ ] Update `services/bid_recommendation_service.py`: `_get_sleeper_draft_context` async
- [ ] Update tests: mock `httpx.AsyncClient` instead of `requests`
- [ ] Verify no `time.sleep` remains in `api/sleeper_api.py`

---

*This note supersedes the original C0 prompt from the Sprint 7 plan. No ADR-002 text change is required — the existing ADR-002 async guidance remains valid.*
