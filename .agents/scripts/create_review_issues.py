#!/usr/bin/env python3
"""
Code Review Issue Creator
Orchestrator-dispatched: creates all code-review GitHub issues discovered
during the Sprint 5 post-commit full-codebase review.

Run from project root:
    python .agents/scripts/create_review_issues.py
"""
import subprocess
import sys
import time

ISSUES = [
    # ── API MODULE ──────────────────────────────────────────────────────────
    {
        "title": "[BUG][P1] api/sleeper_api.py: JSONDecodeError not caught in _make_request — unhandled exception on malformed responses",
        "body": "## Problem\n`_make_request` calls `response.json()` but only catches `requests.RequestException`. If the Sleeper API returns a non-JSON body (e.g., a CloudFlare HTML error page, a plain-text 503, or a Content-Type mismatch), `response.json()` raises `json.JSONDecodeError` which is **not** a subclass of `requests.RequestException` and therefore propagates uncaught through the call stack. Every public method in `SleeperAPI` that calls `_make_request` without its own broad `except Exception` block will crash.\n\n## Location\nFile: api/sleeper_api.py, Lines: 43–53\n\n## Recommendation\nAdd `json.JSONDecodeError` (or `ValueError`, its parent) to the caught exceptions:\n```python\nexcept (requests.RequestException, ValueError) as e:\n    raise SleeperAPIError(f\"API request failed: {e}\") from e\n```\n\n## Acceptance Criteria\n- [ ] `_make_request` catches `json.JSONDecodeError` and wraps it in `SleeperAPIError`\n- [ ] Unit test: mocking a response with `content-type: text/html` and a non-JSON body does not raise an unhandled exception",
        "labels": ["bug", "code-review", "api", "priority:P1"],
    },
    {
        "title": "[BUG][P1] api/sleeper_api.py: search_players / get_player_by_name / bulk_convert_players mutate shared input dicts in-place",
        "body": "## Problem\nBoth `search_players` and `get_player_by_name` execute `player_data['player_id'] = player_id` directly on the dict that came from `players_data` (which is the same object returned by `get_all_players()`). `bulk_convert_players` does the same. This silently mutates the shared data structure. If `get_all_players()` is ever memoised or cached (a natural follow-on optimisation), a second call to `search_players` would find `player_id` already set on cached records. More critically it violates caller expectations: the original `players_data` dict passed in should be read-only from the method's perspective.\n\n## Location\nFile: api/sleeper_api.py, Lines: 205, 223, 302\n\n## Recommendation\nCopy the dict before mutating:\n```python\nplayer_entry = dict(player_data)  # shallow copy\nplayer_entry['player_id'] = player_id\nresults.append(player_entry)\n```\nApply the same pattern in `get_player_by_name` and `bulk_convert_players`.\n\n## Acceptance Criteria\n- [ ] No in-place mutation of the source `players_data` dict\n- [ ] Calling `search_players` twice with a shared dict produces identical results on both calls\n- [ ] `get_player_by_name` and `bulk_convert_players` similarly do not mutate their inputs",
        "labels": ["bug", "code-review", "api", "priority:P1"],
    },
    {
        "title": "[BUG][P2] api/sleeper_api.py: get_trending_players sends 'type' as duplicate query parameter",
        "body": "## Problem\n`get_trending_players` constructs the endpoint as `f\"/players/{sport}/trending/{type_}\"` — `type_` is already encoded as a URL path segment. The `params` dict then adds `'type': type_` again, sending `?type=add` as a redundant query parameter. The Sleeper API `/players/{sport}/trending/{type}` endpoint accepts `lookback_hours` and `limit` as query params, not `type`. Sending an unexpected `type` query param may interfere with future Sleeper API versions and is presently incorrect per the public Sleeper API specification.\n\n## Location\nFile: api/sleeper_api.py, Lines: 163–170\n\n## Recommendation\nRemove `'type': type_` from the `params` dict:\n```python\nparams = {\n    'lookback_hours': hours,\n    'limit': limit\n}\n```\n\n## Acceptance Criteria\n- [ ] `params` dict in `get_trending_players` does not include `'type'`\n- [ ] Unit test verifies the constructed URL contains `type_` only as a path segment",
        "labels": ["bug", "code-review", "api", "priority:P2"],
    },
    {
        "title": "[SECURITY][P1] api/sleeper_api.py: User-supplied strings interpolated into URL paths without encoding — SSRF path traversal risk",
        "body": "## Problem\nValues like `username`, `user_id`, `league_id`, and `draft_id` are directly interpolated into URL paths:\n```python\nreturn self._make_request(f\"/user/{username}\")\nreturn self._make_request(f\"/league/{league_id}/rosters\")\n```\nIf any of these values originate from an HTTP request body or query parameter, a malicious value such as `../../admin` or `%2F..%2F..%2Fadmin` could alter the effective target path on the Sleeper API host, constituting a Server-Side Request Forgery / path traversal (OWASP A10: SSRF).\n\n## Location\nFile: api/sleeper_api.py, Lines: 61, 65, 71, 76, 81, 86, 91, 96, 101, 106, 111, 116, 121\n\n## Recommendation\nURL-encode path segments before interpolation:\n```python\nfrom urllib.parse import quote\n\ndef _safe_path(value: str) -> str:\n    return quote(str(value), safe=\"\")\n\n# Usage:\nreturn self._make_request(f\"/user/{_safe_path(username)}\")\n```\n\n## Acceptance Criteria\n- [ ] All user-supplied path segments are URL-encoded or validated with a strict regex before interpolation\n- [ ] Test: `get_user(\"../../admin\")` does not produce a request to an unexpected path",
        "labels": ["bug", "code-review", "api", "security", "priority:P1"],
    },
    {
        "title": "[SECURITY][P2] api: No authentication or authorization on any endpoint",
        "body": "## Problem\nAll API endpoints (`/health`, `/strategies`, `/players`, `/draft`, `/auction`) are publicly accessible with no authentication layer. There is no API key check, no JWT validation, no OAuth2 scope enforcement. Once the draft and auction routers are implemented, unauthenticated callers will be able to read draft state, place bids, and manipulate budgets. This violates OWASP A01: Broken Access Control.\n\n## Location\nFile: api/main.py (global), api/routers/*.py\n\n## Recommendation\nAdd a FastAPI security dependency at the router or app level. For a minimal approach, implement API-key-in-header:\n```python\n# api/deps.py\nfrom fastapi import Security, HTTPException\nfrom fastapi.security import APIKeyHeader\n\napi_key_header = APIKeyHeader(name=\"X-API-Key\")\n\ndef require_api_key(key: str = Security(api_key_header)) -> str:\n    if key != get_settings().api_key:\n        raise HTTPException(status_code=403, detail=\"Forbidden\")\n    return key\n```\n\n## Acceptance Criteria\n- [ ] All routers except `/health` require a valid credential\n- [ ] 403 is returned for missing or invalid credentials\n- [ ] API key is sourced from `Settings` / env var, never hardcoded",
        "labels": ["enhancement", "code-review", "api", "security", "priority:P2"],
    },
    {
        "title": "[IMPROVEMENT][P1] api/sleeper_api.py: Synchronous requests + time.sleep() block FastAPI event loop",
        "body": "## Problem\n`SleeperAPI` uses the synchronous `requests.Session` and calls `time.sleep()` inside `_make_request`. FastAPI runs on an `asyncio` event loop (via Uvicorn). When any async route handler calls `SleeperAPI` methods, the blocking sleep and blocking HTTP I/O freeze the entire event loop for the duration, preventing all other in-flight requests from being processed. Under moderate load this produces cascading latency spikes.\n\n## Location\nFile: api/sleeper_api.py, Lines: 35–53 (`_make_request`)\n\n## Recommendation\nMigrate to `httpx.AsyncClient` and `asyncio.sleep`. Alternatively, if keeping `requests` synchronously, wrap calls with `asyncio.get_event_loop().run_in_executor(None, ...)` at the router layer and mark all affected route functions `def` (sync), which FastAPI runs in a thread pool.\n\n## Acceptance Criteria\n- [ ] No blocking `time.sleep()` or synchronous HTTP I/O called from async route handlers\n- [ ] HTTP client is either `httpx.AsyncClient` or `SleeperAPI` is explicitly invoked inside `run_in_executor`\n- [ ] Rate-limit delay uses `asyncio.sleep` in async context\n\n_Note: also tracked as P4-4 (httpx migration)_",
        "labels": ["enhancement", "code-review", "api", "priority:P1"],
    },
    {
        "title": "[BUG][P2] api/main.py: /health endpoint missing response_model — HealthResponse schema is dead code",
        "body": "## Problem\nThe `health()` endpoint returns a raw `dict` literal `{\"status\": \"ok\"}` with no `response_model` annotation. `HealthResponse` is defined in `api/schemas/common.py` but is never imported or used anywhere. As a result: (1) the OpenAPI schema documents the response as an opaque object, (2) FastAPI performs no response serialisation or validation, and (3) a future change to the response structure would not be caught at the API layer.\n\n## Location\nFile: api/main.py, Lines: 29–31\n\n## Recommendation\n```python\nfrom api.schemas.common import HealthResponse\n\n@app.get(\"/health\", tags=[\"meta\"], response_model=HealthResponse)\ndef health() -> HealthResponse:\n    return HealthResponse(status=\"ok\")\n```\n\n## Acceptance Criteria\n- [ ] `/health` declares `response_model=HealthResponse`\n- [ ] `HealthResponse` is imported and used in `main.py`\n- [ ] OpenAPI docs show typed response schema for `/health`",
        "labels": ["bug", "code-review", "api", "priority:P2"],
    },
    {
        "title": "[IMPROVEMENT][P2] api/routers/strategies.py: response_model not set — StrategyListResponse schema unused",
        "body": "## Problem\nThe `/strategies/` endpoint returns `list[str]` directly, bypassing `StrategyListResponse` which wraps the list with a `count` field. The schema was designed as the contract for this endpoint but is never referenced. FastAPI will not validate the response, the `count` field is never populated, and the OpenAPI documentation will show `array of string` instead of the richer `StrategyListResponse` object.\n\n## Location\nFile: api/routers/strategies.py, Lines: 7–10\n\n## Recommendation\n```python\nfrom api.schemas.strategies import StrategyListResponse\n\n@router.get(\"/\", response_model=StrategyListResponse)\ndef list_strategies() -> StrategyListResponse:\n    names = list(AVAILABLE_STRATEGIES.keys())\n    return StrategyListResponse(strategies=names, count=len(names))\n```\n\n## Acceptance Criteria\n- [ ] `list_strategies` declares `response_model=StrategyListResponse`\n- [ ] Response body includes both `strategies` list and `count` integer",
        "labels": ["enhancement", "code-review", "api", "priority:P2"],
    },
    {
        "title": "[IMPROVEMENT][P2] api/routers/{players,draft,auction}.py: Placeholder routes return HTTP 200 instead of 501 Not Implemented",
        "body": "## Problem\nAll three placeholder routers return `{\"message\": \"Not yet implemented\"}` with HTTP 200 OK. HTTP 200 signals success to API clients and monitoring tools. A 200 with a human-readable message in the body is invisible to automated consumers (load balancers, health checks, integration tests) that inspect only the status code. The correct status code for an endpoint stub is 501 Not Implemented.\n\n## Location\nFile: api/routers/players.py, Line: 8\nFile: api/routers/draft.py, Line: 8\nFile: api/routers/auction.py, Line: 8\n\n## Recommendation\n```python\nfrom fastapi.responses import JSONResponse\n\n@router.get(\"/\")\ndef list_players():\n    return JSONResponse(status_code=501, content={\"detail\": \"Not yet implemented\"})\n```\n\n## Acceptance Criteria\n- [ ] All three placeholder endpoints return HTTP 501\n- [ ] Response body uses the `ErrorDetail` schema from `api/schemas/common.py`",
        "labels": ["enhancement", "code-review", "api", "priority:P2"],
    },
    {
        "title": "[IMPROVEMENT][P2] api/main.py: No global exception handler — internal errors may leak stack traces",
        "body": "## Problem\nThere is no `@app.exception_handler(Exception)` registered. In FastAPI's default configuration, unhandled exceptions produce a 500 response. Depending on the ASGI server settings, Python tracebacks or internal module paths can appear in the response body in non-production configurations, violating OWASP A05: Security Misconfiguration. The `ErrorDetail` schema in `api/schemas/common.py` is defined but never wired to any error handler.\n\n## Location\nFile: api/main.py\n\n## Recommendation\n```python\n@app.exception_handler(Exception)\nasync def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:\n    return JSONResponse(\n        status_code=500,\n        content=ErrorDetail(\n            title=\"Internal Server Error\",\n            status=500,\n            detail=\"An unexpected error occurred.\",\n            instance=str(request.url)\n        ).model_dump()\n    )\n```\n\n## Acceptance Criteria\n- [ ] Global exception handler registered on the FastAPI app\n- [ ] 500 response uses `ErrorDetail` RFC 7807 schema\n- [ ] Python tracebacks are not exposed in response bodies",
        "labels": ["enhancement", "code-review", "api", "security", "priority:P2"],
    },
    {
        "title": "[IMPROVEMENT][P2] api/deps.py: get_app_settings is dead code — never used by any router",
        "body": "## Problem\n`get_app_settings()` is defined in `api/deps.py` but is not injected via `Depends(get_app_settings)` in any router or endpoint. The function is entirely unused. When settings-aware routes are implemented, developers may not discover this dep exists and will duplicate the logic directly, creating inconsistency.\n\n## Location\nFile: api/deps.py, Lines: 4–5\n\n## Recommendation\nEither (a) remove the function until it is actually needed, or (b) immediately wire it into at least one router that needs settings.\n\n## Acceptance Criteria\n- [ ] `get_app_settings` is either deleted or actively used by at least one route\n- [ ] No unused public symbols in `api/deps.py`",
        "labels": ["enhancement", "code-review", "api", "priority:P2"],
    },
    {
        "title": "[IMPROVEMENT][P2] api/schemas/draft.py: strategy_type is a free-text string with no enum validation",
        "body": "## Problem\n`DraftCreateRequest.strategy_type` accepts any arbitrary string (default `\"value\"`). Invalid values such as `\"hax\"` or an empty string pass schema validation and are only rejected deep in business logic — or silently fall back to a default, masking the input error. This violates the principle of validating at system boundaries.\n\n## Location\nFile: api/schemas/draft.py, Lines: 8–12\n\n## Recommendation\nUse a `Literal` or `Enum` bound to `AVAILABLE_STRATEGIES`:\n```python\n# Or add a @field_validator that checks against AVAILABLE_STRATEGIES.keys()\nclass DraftCreateRequest(BaseModel):\n    strategy_type: str = \"value\"\n\n    @field_validator('strategy_type')\n    @classmethod\n    def validate_strategy(cls, v):\n        if v not in AVAILABLE_STRATEGIES:\n            raise ValueError(f\"Unknown strategy: {v}\")\n        return v\n```\n\n## Acceptance Criteria\n- [ ] `strategy_type` rejects unknown values with a 422 response and a descriptive message\n- [ ] Valid strategy names are reflected in the OpenAPI schema",
        "labels": ["enhancement", "code-review", "api", "priority:P2"],
    },
    {
        "title": "[PERFORMANCE][P2] api/sleeper_api.py: get_all_players() called on every search with no caching",
        "body": "## Problem\n`search_players()`, `get_player_by_name()`, and `bulk_convert_players()` each call `self.get_all_players()` when no `players_data` argument is provided. `get_all_players()` makes a full HTTP round-trip to `GET /players/nfl` which returns ~1,500+ player records (typically 3–5 MB of JSON). There is no memoisation, TTL cache, or class-level cache. A single page load that calls both `search_players` and `bulk_convert_players` will issue two separate full-download requests.\n\n## Location\nFile: api/sleeper_api.py, Lines: 197, 218, 298\n\n## Recommendation\nAdd a TTL-aware instance cache (e.g., `cachetools.TTLCache` or a simple timestamp-guarded dict) on `get_all_players()` with a default TTL of at least 1 hour.\n\n## Acceptance Criteria\n- [ ] `get_all_players()` result is cached for a configurable TTL\n- [ ] Cache is invalidatable via an explicit method or TTL expiry\n- [ ] Unit tests can inject a pre-populated cache to avoid real network calls",
        "labels": ["enhancement", "code-review", "api", "priority:P2"],
    },
    {
        "title": "[IMPROVEMENT][P3] api/sleeper_api.py: Hardcoded default season '2024' will produce stale data in future years",
        "body": "## Problem\n`get_player_stats(season=\"2024\")` and `get_player_projections(season=\"2024\")` hardcode the season year as a magic string default. When the 2025+ season begins, callers that rely on the default will silently receive historical data without any warning or error.\n\n## Location\nFile: api/sleeper_api.py, Lines: 174, 185\n\n## Recommendation\nDerive the current season dynamically from `get_nfl_state()` or source it from `config/settings.py`:\n```python\ndef _current_season(self) -> str:\n    state = self.get_nfl_state()\n    return str(state.get('season', datetime.date.today().year)) if state else str(datetime.date.today().year)\n```\n\n## Acceptance Criteria\n- [ ] Default season is not a hardcoded literal\n- [ ] Season can be overridden per-call\n- [ ] `Settings` in `config/settings.py` has a `default_season` field as fallback",
        "labels": ["enhancement", "code-review", "api", "priority:P3"],
    },
    {
        "title": "[IMPROVEMENT][P3] api/schemas/auction.py: BidRequest fields lack minimum content validation — empty strings and over-budget bids accepted",
        "body": "## Problem\n`BidRequest.player_id` and `BidRequest.team_name` are plain `str` fields with no `min_length` constraint. Both accept empty strings (`\"\"`), which will cause downstream failures in auction logic. The `bid_amount` has `ge=1` but no upper bound, allowing arbitrarily large bids that would violate any league budget cap without being caught at the schema layer.\n\n## Location\nFile: api/schemas/auction.py, Lines: 6–9\n\n## Recommendation\n```python\nclass BidRequest(BaseModel):\n    player_id: str = Field(min_length=1, max_length=100)\n    bid_amount: int = Field(ge=1, le=10000)  # configure upper bound from settings\n    team_name: str = Field(min_length=1, max_length=100)\n```\n\n## Acceptance Criteria\n- [ ] Empty `player_id` or `team_name` returns HTTP 422\n- [ ] `bid_amount` exceeding a configured maximum returns HTTP 422",
        "labels": ["enhancement", "code-review", "api", "priority:P3"],
    },

    # ── CLASSES MODULE ──────────────────────────────────────────────────────
    {
        "title": "[BUG][P0] classes/tournament.py: strategies registered on Auction but run_complete_draft uses Team.strategy — all bids are $0, rosters stay empty",
        "body": "## Problem\n`_run_single_simulation` configures strategies via `auction.enable_auto_bid(owner_id, strategy)`, which stores them in `Auction.strategies`. However, `auction.start_auction()` calls `draft.run_complete_draft()` synchronously, and that method uses `team.calculate_bid()` → `team.strategy`. Since `team.strategy` is never set (only `auction.strategies` is), every `calculate_bid` call returns `0`. Every player is stripped from `available_players` without being awarded to any team. All simulations complete with empty rosters and 0 projected points, making tournament results entirely meaningless.\n\n## Location\nFile: classes/tournament.py, Lines: 171–192 (`_run_single_simulation`)\n\n## Recommendation\nSet `team.strategy` directly on the `Team` object when building the simulation: `team.set_strategy(strategy)`. Alternatively, restructure so strategies are attached to teams before `draft.start_draft()` is called.\n\n## Acceptance Criteria\n- [ ] After fix, `_run_single_simulation` produces teams with non-empty rosters\n- [ ] `Tournament.run_tournament()` returns results with non-zero `avg_points` for each strategy\n- [ ] Existing tournament tests pass",
        "labels": ["bug", "code-review", "classes", "priority:P0"],
    },
    {
        "title": "[BUG][P1] classes/draft.py: complete_auction ignores add_player return value — player silently lost from draft pool on failure",
        "body": "## Problem\n`complete_auction` calls `winner_team.add_player(player, final_price)` but discards the boolean return value. `Team.add_player` returns `False` if budget is insufficient or `_can_add_player` rejects the player. When `add_player` returns `False`, the code still executes `self.available_players.remove(player)` and `self.drafted_players.append(player)`. The player vanishes from the available pool, is counted as drafted, but appears on no team's roster and the team's budget is unchanged — a permanent data corruption of draft state.\n\n## Location\nFile: classes/draft.py, Lines: 182–191 (`complete_auction`)\n\n## Recommendation\n```python\nif not winner_team.add_player(player, final_price):\n    logger.error(\"add_player failed for %s to %s at $%s — re-queuing\",\n                 player.name, winner_team.team_name, final_price)\n    return  # Do NOT remove from available_players\nself.available_players.remove(player)\nself.drafted_players.append(player)\n```\n\n## Acceptance Criteria\n- [ ] When `add_player` returns `False`, player remains in `available_players`\n- [ ] `len(drafted_players) + len(available_players)` always equals original player pool size",
        "labels": ["bug", "code-review", "classes", "priority:P1"],
    },
    {
        "title": "[BUG][P1] classes/team.py: QB bench constraint is unreachable dead code — unlimited QBs can be added to bench",
        "body": "## Problem\n`_can_fit_in_roster_structure` contains a dead code block after `return False  # No available slots` that is the ONLY place enforcing the QB bench constraint:\n```python\n# This code is UNREACHABLE — follows a return statement\nif pos == 'QB':\n    qb_on_bench = max(0, current_counts.get('QB', 0) - direct_needed)\n    if qb_on_bench >= 1:\n        return False  # Already have max QBs on bench\n```\nThe live code path has no such guard. A team can hoard every QB in the player pool, violating the domain invariant.\n\n## Location\nFile: classes/team.py, Lines: 420–467 (unreachable block)\n\n## Recommendation\nDelete the unreachable block. Move the QB bench constraint into the live BN/BENCH check immediately above the `return False` that precedes the dead block.\n\n## Acceptance Criteria\n- [ ] Dead code block is removed\n- [ ] QB bench constraint is enforced in the live code path\n- [ ] Adding a third QB to a standard roster is rejected",
        "labels": ["bug", "code-review", "classes", "priority:P1"],
    },
    {
        "title": "[BUG][P1] classes/team.py: is_roster_complete and get_needs use hardcoded position requirements, ignoring roster_config",
        "body": "## Problem\nBoth `is_roster_complete()` and `get_needs()` define an internal `required_positions` dict hardcoded to `{'QB': 1, 'RB': 2, 'WR': 2, 'TE': 1, 'K': 1, 'DST': 1}` and never reference `self.roster_config`. A 2-QB league will declare a roster complete after only 1 QB. `_is_draft_complete()` in `Draft` calls `team.is_roster_complete()`, so the entire draft completion check is wrong for non-standard leagues.\n\n## Location\nFile: classes/team.py, Lines: 203–215 (`is_roster_complete`), Lines: 219–233 (`get_needs`)\n\n## Recommendation\nReplace the hardcoded dict with `self._get_required_positions()`, which already exists and respects `self.roster_config`.\n\n## Acceptance Criteria\n- [ ] `is_roster_complete()` returns `False` for a 2-QB league with only 1 QB\n- [ ] `get_needs()` returns correct unfilled positions for custom roster configs",
        "labels": ["bug", "code-review", "classes", "priority:P1"],
    },
    {
        "title": "[BUG][P1] classes/tournament.py: get_strategy_rankings divides by zero when only one strategy config is present",
        "body": "## Problem\n`get_strategy_rankings` computes:\n```python\nranking_score = (1 - (results['avg_ranking'] - 1) / (len(self.strategy_configs) - 1)) * 20\n```\nWhen `len(self.strategy_configs) == 1`, the denominator is `0`, raising `ZeroDivisionError`. This crashes any call to `run_tournament()` when only a single strategy type is being benchmarked — a common use case for regression testing.\n\n## Location\nFile: classes/tournament.py, Line: 294 (`get_strategy_rankings`)\n\n## Recommendation\n```python\nif len(self.strategy_configs) > 1:\n    ranking_score = (1 - (results['avg_ranking'] - 1) / (len(self.strategy_configs) - 1)) * 20\nelse:\n    ranking_score = 20.0\n```\n\n## Acceptance Criteria\n- [ ] `get_strategy_rankings()` does not raise when `len(strategy_configs) == 1`\n- [ ] Existing multi-strategy ranking tests still pass",
        "labels": ["bug", "code-review", "classes", "priority:P1"],
    },
    {
        "title": "[BUG][P1] classes/player.py: Player.__init__ name default '' violates Field(min_length=1) — ValidationError on default construction",
        "body": "## Problem\nThe Pydantic field declares `name: str = Field(min_length=1)`, enforcing a minimum length of 1. The custom `__init__` provides `name: str = ''` as its default value. Calling `Player(player_id='x')` passes `name=''` to Pydantic, which raises `ValidationError`. The constructor signature implies `name` is optional, but using the default is always an error.\n\n## Location\nFile: classes/player.py, Line: 13 (field declaration), Line: 32 (`__init__` signature)\n\n## Recommendation\nRemove the default so `name` is a required argument:\n```python\ndef __init__(self, player_id: str, name: str, ...):\n    # name is required — no default\n```\n\n## Acceptance Criteria\n- [ ] `Player(player_id='x')` raises a clear `TypeError` (missing required arg)\n- [ ] No silent `ValidationError` is produced during normal construction flows",
        "labels": ["bug", "code-review", "classes", "priority:P1"],
    },
    {
        "title": "[BUG][P2] classes/auction.py: _determine_auction_winner charges top_bid + 1 on ties — winner pays more than their stated max bid",
        "body": "## Problem\n`Auction._determine_auction_winner` handles tied top bids as:\n```python\nif len(tied_winners) > 1:\n    return winner_id, top_bid + 1.0  # winner pays TOP + 1\n```\nThis means the winner pays MORE than they bid, violating the Vickrey auction invariant. Furthermore `Draft._determine_auction_winner` (the parallel implementation) charges `top_bid` on ties — the two implementations are inconsistent. In a scenario where `top_bid == team.budget`, the winner would be charged past their budget, causing `Team.add_player` to silently return `False`.\n\n## Location\nFile: classes/auction.py, Lines: 408–413\nFile: classes/draft.py, Lines: 305–318\n\n## Recommendation\nRemove the `+ 1.0` on ties. Bid price should never exceed the winner's stated max:\n```python\nif len(tied_winners) > 1:\n    return winner_id, top_bid  # tied — pay the tied amount\n```\nConsolidate the two implementations into a shared utility.\n\n## Acceptance Criteria\n- [ ] Winner on a tie pays `top_bid`, not `top_bid + 1`\n- [ ] Both `_determine_auction_winner` implementations produce identical results\n- [ ] Bid price never exceeds the winner's stated max bid",
        "labels": ["bug", "code-review", "classes", "priority:P2"],
    },
    {
        "title": "[BUG][P2] classes/tournament.py: single strategy instance shared across multiple teams — mutable strategy state corrupted within simulation",
        "body": "## Problem\nIn `_run_single_simulation`, one `strategy` instance is created per strategy type and assigned to every team of that type:\n```python\nstrategy = create_strategy(config['strategy_type'])  # one instance\nfor i in range(config['num_teams']):\n    auction.enable_auto_bid(owner_id, strategy)  # same ref for N teams\n```\nStrategies that maintain mutable internal state (budget history, bid counters, learning weights) will have that state clobbered by interleaved calls from different teams. Results produced by shared-state strategies are not reproducible and are statistically invalid.\n\n## Location\nFile: classes/tournament.py, Lines: 177–184 (`_run_single_simulation`)\n\n## Recommendation\nCreate a separate strategy instance per team:\n```python\nfor i in range(config['num_teams']):\n    strategy = create_strategy(config['strategy_type'])  # fresh per team\n    ...\n```\n\n## Acceptance Criteria\n- [ ] Each team in a simulation gets its own independent strategy instance\n- [ ] Re-running the same simulation produces deterministic results when `random.seed` is fixed",
        "labels": ["bug", "code-review", "classes", "priority:P2"],
    },
    {
        "title": "[BUG][P2] classes/team.py: remove_player does not reset draft_price alias — drafted_price and draft_price diverge",
        "body": "## Problem\n`remove_player` resets `player.drafted_price = None` but does not touch `player.draft_price` (the backward-compatibility alias). After `remove_player`, the two fields hold different values: `drafted_price=None` and `draft_price=<original price>`. Any code that reads `draft_price` after an un-draft will see stale data.\n\n## Location\nFile: classes/team.py, Lines: 92–103 (`remove_player`)\n\n## Recommendation\nAdd `player.draft_price = None` to `remove_player`, mirroring the sync already done in `mark_as_drafted`.\n\n## Acceptance Criteria\n- [ ] After `remove_player`, both `player.draft_price` and `player.drafted_price` are `None`\n- [ ] Both fields remain in sync after a full draft → un-draft → re-draft cycle",
        "labels": ["bug", "code-review", "classes", "priority:P2"],
    },
    {
        "title": "[BUG][P2] classes/owner.py: to_dict roster_spots embeds raw Player Pydantic objects — json.dumps raises TypeError",
        "body": "## Problem\n`Owner.to_dict()` calls `self.get_roster_spots()`, which returns dicts containing `{'player': <Player object>}`. The `Player` value is a live Pydantic model instance, not a plain dict. When the result is passed to `json.dumps()` (as in any API response or export), Python raises `TypeError: Object of type Player is not JSON serializable`.\n\n## Location\nFile: classes/owner.py, Lines: 100–122 (`get_roster_spots`), Line: 165 (`to_dict`)\n\n## Recommendation\nConvert each Player to a dict inside `get_roster_spots`:\n```python\n'player': player.to_dict() if player else None,\n```\n\n## Acceptance Criteria\n- [ ] `json.dumps(owner.to_dict())` succeeds without TypeError for a roster-full owner\n- [ ] `player` values in roster_spots are plain dicts, not Pydantic models",
        "labels": ["bug", "code-review", "classes", "priority:P2"],
    },
    {
        "title": "[BUG][P2] classes/tournament.py: _analyze_results extracts strategy key via owner_id.split('_')[0] — wrong key for multi-word strategy names",
        "body": "## Problem\n`_analyze_results` parses the strategy type from `owner_id` using:\n```python\nstrategy_type = owner_id.split('_')[0]\n```\nIf strategy type strings like `\"value_based\"`, `\"enhanced_vor\"`, `\"elite_hybrid\"` contain underscores, `split('_')[0]` returns only the first word segment (e.g., `\"value\"` instead of `\"value_based\"`). This causes distinct strategies to be merged into a single results bucket, producing completely wrong performance statistics.\n\n## Location\nFile: classes/tournament.py, Lines: 213–216 (`_analyze_results`)\n\n## Recommendation\nStore the strategy type as an explicit tag on `Owner` or `Team` at simulation creation time and read it back during analysis, rather than re-parsing the ID string.\n\n## Acceptance Criteria\n- [ ] Strategy names containing underscores produce separate result buckets\n- [ ] `run_strategy_comparison(['value_based', 'aggressive'])` returns 2 distinct result entries",
        "labels": ["bug", "code-review", "classes", "priority:P2"],
    },
    {
        "title": "[IMPROVEMENT][P2] classes/player.py: to_dict omits vor field — VOR data silently lost on serialization round-trips",
        "body": "## Problem\n`Player.to_dict()` returns a dict that omits `vor`. Since strategies heavily rely on `vor` for bid calculations (and `vor` was explicitly added as a tracked field in Sprint 5 via #90), any round-trip through `to_dict()` (e.g., export → reimport, API response deserialization) loses VOR values, silently resetting them to the `0.0` default.\n\n## Location\nFile: classes/player.py, Lines: 88–103 (`to_dict`)\n\n## Recommendation\nAdd `vor` to the returned dict:\n```python\nreturn {\n    ...\n    'vor': self.vor,\n    ...\n}\n```\n\n## Acceptance Criteria\n- [ ] `player.to_dict()` includes `'vor'` key\n- [ ] Round-tripping a player with non-zero `vor` through `to_dict()` → `Player(**d)` preserves the VOR value",
        "labels": ["enhancement", "code-review", "classes", "priority:P2"],
    },
    {
        "title": "[IMPROVEMENT][P2] classes/tournament.py: post-start_auction simulation loop is dead code — run_complete_draft already completes synchronously",
        "body": "## Problem\n`_run_single_simulation` calls `auction.start_auction()`, which internally calls `draft.run_complete_draft()` synchronously and only returns after `draft.status == 'completed'`. The code immediately after is a while-loop:\n```python\nwhile draft.status == \"started\" and iterations < max_iterations:\n    ...\n```\nSince `draft.status` is `\"completed\"` when `start_auction()` returns, the while condition is immediately `False` and the loop body never executes. All the nomination-forcing and auto-bid logic inside the loop is dead code.\n\n## Location\nFile: classes/tournament.py, Lines: 192–208 (`_run_single_simulation`)\n\n## Recommendation\nRemove the dead while-loop entirely.\n\n## Acceptance Criteria\n- [ ] Dead while-loop is removed\n- [ ] Simulation still completes successfully\n- [ ] No behavioral change in tournament output",
        "labels": ["enhancement", "code-review", "classes", "priority:P2"],
    },
    {
        "title": "[IMPROVEMENT][P3] classes/player.py: player_id_not_none validator is dead code in Pydantic v2",
        "body": "## Problem\n```python\n@field_validator('player_id')\n@classmethod\ndef player_id_not_none(cls, v: str) -> str:\n    if v is None:\n        raise ValueError(\"player_id cannot be None\")\n    return v\n```\n`player_id` is typed as `str` (not `Optional[str]`). In Pydantic v2, a non-optional `str` field rejects `None` with a type validation error before any `@field_validator` is called. The `if v is None` branch is unreachable.\n\n## Location\nFile: classes/player.py, Lines: 56–60\n\n## Recommendation\nRemove the validator entirely. If an explicit `None` guard is wanted, use `player_id: str = Field(min_length=1)`.\n\n## Acceptance Criteria\n- [ ] `player_id_not_none` validator is removed\n- [ ] `Player(player_id=None, ...)` still raises a Pydantic validation error",
        "labels": ["enhancement", "code-review", "classes", "priority:P3"],
    },
    {
        "title": "[IMPROVEMENT][P3] classes/draft_setup.py: calculate_auction_values uses magic number 2400.0 — breaks for non-12-team / non-$200 leagues",
        "body": "## Problem\n`calculate_auction_values` defaults `total_budget=2400.0` (12 teams × $200 hardcoded). Leagues with different team counts or budgets receive silently wrong auction values. There is no documentation or assertion warning about this assumption.\n\n## Location\nFile: classes/draft_setup.py, Lines: 204–245 (`calculate_auction_values`)\n\n## Recommendation\nReplace the magic number with explicit parameters:\n```python\n@staticmethod\ndef calculate_auction_values(\n    players: List[Player],\n    num_teams: int = 12,\n    budget_per_team: float = 200.0\n) -> None:\n    total_budget = num_teams * budget_per_team\n```\n\n## Acceptance Criteria\n- [ ] `calculate_auction_values` accepts `num_teams` and `budget_per_team`\n- [ ] Default behavior matches current output for 12-team $200 leagues\n- [ ] Calling with `num_teams=8` produces proportionally smaller auction values",
        "labels": ["enhancement", "code-review", "classes", "priority:P3"],
    },
    {
        "title": "[IMPROVEMENT][P3] classes/draft_setup.py: unconditional top-level import of SleeperAPI couples entire classes package to API layer",
        "body": "## Problem\n`draft_setup.py` has `from api.sleeper_api import SleeperAPI` as an unconditional top-level import. Because `classes/__init__.py` imports `DraftSetup`, importing any class from `classes` transitively imports `api.sleeper_api`. If that module is unavailable, the entire `classes` package fails to import. This also creates a circular-import risk if `api/` modules ever import from `classes/`.\n\n## Location\nFile: classes/draft_setup.py, Line: 11\n\n## Recommendation\nMove the import inside the method that actually uses it (`import_players_from_sleeper`), making it a lazy import:\n```python\ndef import_players_from_sleeper(...) -> List[Player]:\n    from api.sleeper_api import SleeperAPI  # lazy\n    ...\n```\n\n## Acceptance Criteria\n- [ ] `from classes import Player` succeeds even when `api/sleeper_api.py` cannot be imported\n- [ ] `import_players_from_sleeper()` still works correctly at runtime",
        "labels": ["enhancement", "code-review", "classes", "priority:P3"],
    },

    # ── SERVICES MODULE ─────────────────────────────────────────────────────
    {
        "title": "[BUG][P0] services/bid_recommendation_service.py: Team constructor args misordered in _create_team_from_sleeper_context — budget silently ignored",
        "body": "## Problem\n`_create_team_from_sleeper_context` calls `Team(team_name, \"user_id\", budget)` with only three positional arguments. `Team.__init__` signature is `(team_id, owner_id, team_name, budget=200)`, so:\n- `team_id` receives `\"Your Team\"` (correct)\n- `owner_id` receives `\"user_id\"` (correct)\n- `team_name` receives the **integer** `budget` (e.g. `180`), making team name an integer\n- `budget` receives the default `200` — the actual Sleeper `user_budget` is **silently ignored**\n\nEvery Sleeper-context bid recommendation uses a $200 budget regardless of how much the user has already spent.\n\n## Location\nFile: services/bid_recommendation_service.py, Line(s): ~683–688\n\n## Recommendation\n```python\nteam = Team(\n    team_id=\"sleeper_user\",\n    owner_id=\"user_id\",\n    team_name=team_name,\n    budget=budget\n)\n```\n\n## Acceptance Criteria\n- [ ] `Team` is constructed with `team_name` as the `team_name` arg and `budget` as the `budget` arg\n- [ ] Unit test asserts `team.budget == sleeper_context['user_budget']` after the call",
        "labels": ["bug", "code-review", "services", "priority:P0"],
    },
    {
        "title": "[BUG][P1] services/bid_recommendation_service.py: _convert_sleeper_player_to_auction_format uses hardcoded projections for all players",
        "body": "## Problem\nEvery player converted from Sleeper data gets `projected_points=100.0` and `auction_value=10.0` unconditionally. This means every player appears equal to the bidding strategy, producing identical (meaningless) bid recommendations for superstars and waiver-wire players alike. All Sleeper-context bid recommendations are incorrect.\n\n## Location\nFile: services/bid_recommendation_service.py, Line(s): ~658–672\n\n## Recommendation\nUse the Sleeper player's actual projection data when available, falling back to defaults only if absent:\n```python\nprojected_points = float(sleeper_player.get('projected_points') or 100.0)\nauction_value = float(sleeper_player.get('auction_value') or 10.0)\n```\n\n## Acceptance Criteria\n- [ ] Players with non-default projection data use those values\n- [ ] Bid recommendations differ between high-value and low-value players in Sleeper context",
        "labels": ["bug", "code-review", "services", "priority:P1"],
    },
    {
        "title": "[BUG][P1] services/bid_recommendation_service.py: _get_sleeper_draft_context mutates shared player cache dict",
        "body": "## Problem\n`target_player['player_id'] = player_id` writes directly into the dict returned from `get_sleeper_players()`. If the cache returns a reference to an internal dict (not a copy), this permanently mutates the cached entry. Subsequent calls will find the injected `player_id` key on future lookups, and in a multi-threaded context the mutation is a data race.\n\n## Location\nFile: services/bid_recommendation_service.py, Line(s): ~432–447\n\n## Recommendation\n```python\ntarget_player = dict(players_data[player_id])  # copy, not reference\ntarget_player['player_id'] = player_id\n```\n\n## Acceptance Criteria\n- [ ] `players_data[player_id]` is never mutated directly\n- [ ] Test confirms the original cache dict does not contain `player_id` after the call",
        "labels": ["bug", "code-review", "services", "priority:P1"],
    },
    {
        "title": "[BUG][P1] services/bid_recommendation_service.py: user_budget hardcoded to 200, ignores config.budget",
        "body": "## Problem\nIn `_get_sleeper_draft_context`, `user_budget = 200` is set unconditionally as the starting auction budget. The config already has a `budget` field, but it is never consulted here. Leagues with non-standard budgets ($100 or $500) will get bid recommendations calibrated against the wrong total budget.\n\n## Location\nFile: services/bid_recommendation_service.py, Line(s): ~463–465\n\n## Recommendation\n```python\nconfig = self.config_manager.load_config()\nuser_budget = config.budget\n```\n\n## Acceptance Criteria\n- [ ] `user_budget` is initialised from `config.budget`, not a magic literal\n- [ ] Leagues with `budget != 200` produce correctly scaled bid recommendations",
        "labels": ["bug", "code-review", "services", "priority:P1"],
    },
    {
        "title": "[BUG][P1] services/draft_loading_service.py: _calculate_position_limits triple-counts FLEX spots",
        "body": "## Problem\n`FLEX` spots are added to the starting counts of RB, WR, and TE simultaneously:\n```python\n'RB': roster_positions.get('RB', 2) + roster_positions.get('FLEX', 0),\n'WR': roster_positions.get('WR', 2) + roster_positions.get('FLEX', 0),\n'TE': roster_positions.get('TE', 1) + roster_positions.get('FLEX', 0),\n```\nFor a league with 1 FLEX slot, each position gains 1 extra starting spot, so total computed starting capacity grows by 3 instead of 1. This inflates position limits.\n\n## Location\nFile: services/draft_loading_service.py, Line(s): ~185–195\n\n## Recommendation\nFLEX should be treated as a single additional slot shared among eligible positions, not added to each. Track FLEX as its own position limit key instead.\n\n## Acceptance Criteria\n- [ ] A roster config with 1 FLEX slot increases total computed starting capacity by exactly 1\n- [ ] Unit test covers 1 FLEX slot and verifies total starters == sum of all individual starting positions",
        "labels": ["bug", "code-review", "services", "priority:P1"],
    },
    {
        "title": "[BUG][P1] services/draft_loading_service.py: get_draft_status crashes when data_path is None",
        "body": "## Problem\n`get_draft_status` calls `os.path.exists(config.data_path)` unconditionally. When the data source is `\"sleeper\"`, `data_path` is not required and may be `None`. `os.path.exists(None)` raises `TypeError: expected str, bytes or os.PathLike object, not NoneType`.\n\n## Location\nFile: services/draft_loading_service.py, Line(s): ~247\n\n## Recommendation\n```python\n'fantasypros_configured': bool(config.data_path and os.path.exists(config.data_path))\n```\n\n## Acceptance Criteria\n- [ ] `get_draft_status()` returns a valid dict when `config.data_path` is `None`\n- [ ] `fantasypros_configured` is `False` (not an exception) when `data_path` is absent",
        "labels": ["bug", "code-review", "services", "priority:P1"],
    },
    {
        "title": "[BUG][P1] services/draft_loading_service.py: module-level load_draft_from_config starts background timers",
        "body": "## Problem\nThe module-level convenience function `load_draft_from_config` creates `Auction(draft)` without `timer_duration=0`, which starts live countdown timers. This will fire timer callbacks, potentially spawn threads, and cause unexpected behavior when the function is called from tests, CLI, or the FastAPI layer. The class method version correctly uses `Auction(draft, timer_duration=0)`.\n\n## Location\nFile: services/draft_loading_service.py, Line(s): ~326 (module-level function)\n\n## Recommendation\n```python\nauction = Auction(draft, timer_duration=0)\n```\n\n## Acceptance Criteria\n- [ ] The module-level `load_draft_from_config` passes `timer_duration=0`\n- [ ] No background timer threads are started when called from tests or API handlers",
        "labels": ["bug", "code-review", "services", "priority:P1"],
    },
    {
        "title": "[BUG][P1] services/tournament_service.py: _analyze_tournament_results raises KeyError when points_std absent",
        "body": "## Problem\n```python\nmost_consistent = min(rankings, key=lambda x: x[1]['results']['points_std'])\n```\nIf `Tournament.get_strategy_rankings()` returns results where any strategy's `results` dict does not contain `points_std` (e.g., a strategy that completed zero simulations), this raises `KeyError: 'points_std'` inside `_analyze_tournament_results`.\n\n## Location\nFile: services/tournament_service.py, Line(s): ~379\n\n## Recommendation\n```python\nmost_consistent = min(\n    rankings,\n    key=lambda x: x[1]['results'].get('points_std', float('inf'))\n)\n```\n\n## Acceptance Criteria\n- [ ] `_analyze_tournament_results` does not raise `KeyError` when `points_std` is missing\n- [ ] `most_consistent` is `None` or omitted when no std-dev data is available",
        "labels": ["bug", "code-review", "services", "priority:P1"],
    },
    {
        "title": "[SECURITY][P2] services/tournament_service.py: _save_tournament_results writes to CWD-relative path — data escapes project tree",
        "body": "## Problem\n`filepath = os.path.join(\"results\", filename)` is relative to the process's current working directory. When invoked from a different CWD (FastAPI, CLI subcommand, test), `os.makedirs(\"results\", exist_ok=True)` will silently create a directory in an arbitrary location. Data may be written outside the project tree.\n\n## Location\nFile: services/tournament_service.py, Line(s): ~432–443\n\n## Recommendation\nAnchor the path to the project root:\n```python\nPROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))\nfilepath = os.path.join(PROJECT_ROOT, \"results\", filename)\n```\n\n## Acceptance Criteria\n- [ ] Tournament results are always written to `<project_root>/results/` regardless of CWD\n- [ ] No `results/` directory is created outside the project tree",
        "labels": ["bug", "code-review", "services", "security", "priority:P2"],
    },
    {
        "title": "[IMPROVEMENT][P2] services/sleeper_draft_service.py: hardcoded default season '2024' is stale",
        "body": "## Problem\nAll public methods default to `season: str = \"2024\"`. As of 2025+, callers who rely on the default receive data for a historical season and will see empty result sets, silently, with no indication that the season is wrong.\n\n## Location\nFile: services/sleeper_draft_service.py, Lines: 26, 145, 186, 337–350\n\n## Recommendation\n```python\nfrom datetime import datetime\nDEFAULT_SEASON = str(datetime.now().year)\n```\nUse `DEFAULT_SEASON` consistently across all methods.\n\n## Acceptance Criteria\n- [ ] Default season reflects the current calendar year\n- [ ] Module-level constant `DEFAULT_SEASON` used consistently",
        "labels": ["enhancement", "code-review", "services", "priority:P2"],
    },
    {
        "title": "[IMPROVEMENT][P2] services/sleeper_draft_service.py: missing None-guard on get_league_users result before dict comprehension",
        "body": "## Problem\n```python\nusers = self.sleeper_api.get_league_users(league_id)\nusers_info = {user['user_id']: user for user in users}  # TypeError if users is None\n```\nIf `get_league_users` returns `None` (API error, empty league, or network failure), iterating over `None` raises `TypeError`. The same pattern appears in both `display_draft_info` and `display_league_rosters`.\n\n## Location\nFile: services/sleeper_draft_service.py, Lines: ~109, ~147\n\n## Recommendation\n```python\nusers = self.sleeper_api.get_league_users(league_id) or []\n```\n\n## Acceptance Criteria\n- [ ] `get_league_users` returning `None` results in `users_info = {}` not a TypeError\n- [ ] Guard applied in both `display_draft_info` and `display_league_rosters`",
        "labels": ["enhancement", "code-review", "services", "priority:P2"],
    },
    {
        "title": "[IMPROVEMENT][P2] services/bid_recommendation_service.py: recommend_bid and recommend_nomination swallow exceptions without logging",
        "body": "## Problem\nBoth `recommend_bid` and `recommend_nomination` wrap their entire bodies in `except Exception as e` and return `_error_response(...)` with the exception string. No `logger.exception` or `logger.error` call is made, so stack traces are lost. In production this makes diagnosing failures impossible.\n\n## Location\nFile: services/bid_recommendation_service.py, Lines: ~78–82, ~179–181\n\n## Recommendation\n```python\nexcept Exception as e:\n    logger.exception(\"Error generating bid recommendation for '%s'\", player_name)\n    return self._error_response(f\"Error generating bid recommendation: {e}\")\n```\nAlso add a module-level `logger = logging.getLogger(__name__)`.\n\n## Acceptance Criteria\n- [ ] `logger = logging.getLogger(__name__)` defined at module level\n- [ ] All top-level `except Exception` blocks call `logger.exception` before returning error response",
        "labels": ["enhancement", "code-review", "services", "priority:P2"],
    },
    {
        "title": "[IMPROVEMENT][P2] services/tournament_service.py: stop_tournament does not terminate parallel workers",
        "body": "## Problem\n`stop_tournament` sets `self.current_tournament.is_running = False` but `run_strategy_tournament` always invokes `run_tournament(parallel=True)`. Thread pool workers dispatched for parallel simulation continue running after `stop_tournament` returns. The flag has no effect on already-dispatched work items, making `stop_tournament` a no-op for in-flight simulations.\n\n## Location\nFile: services/tournament_service.py, Lines: ~226–237\n\n## Recommendation\nEither expose a cancellation mechanism on `Tournament` (e.g. a threading `Event`) and check it in each simulation iteration, or document the limitation explicitly.\n\n## Acceptance Criteria\n- [ ] `stop_tournament` either genuinely stops in-flight workers or its docstring accurately states it only prevents new work",
        "labels": ["enhancement", "code-review", "services", "priority:P2"],
    },
    {
        "title": "[IMPROVEMENT][P3] services/tournament_service.py: num_simulations not validated — zero/negative values accepted",
        "body": "## Problem\n`run_strategy_tournament` and `run_custom_tournament` accept `num_simulations` without range validation. Passing `num_simulations=0` or `-1` produces a degenerate tournament that causes division-by-zero in win-rate calculations inside `Tournament.run_tournament`.\n\n## Location\nFile: services/tournament_service.py, Lines: ~33, ~122\n\n## Recommendation\n```python\nif num_simulations < 1:\n    return {'success': False, 'error': 'num_simulations must be >= 1'}\n```\n\n## Acceptance Criteria\n- [ ] `num_simulations <= 0` returns `{'success': False, 'error': ...}` immediately\n- [ ] Unit test covers `num_simulations=0`",
        "labels": ["enhancement", "code-review", "services", "priority:P3"],
    },
    {
        "title": "[IMPROVEMENT][P3] services/bid_recommendation_service.py: duplicate convenience functions are dead code",
        "body": "## Problem\nThe module defines two pairs of functionally identical convenience functions:\n- `recommend_bid` / `get_bid_recommendation` — identical signatures and bodies\n- `recommend_nomination` / `get_nomination_recommendation` — identical signatures and bodies\n\n`__init__.py` exports only the `get_*` variants. The `recommend_*` variants are unreferenced dead code.\n\n## Location\nFile: services/bid_recommendation_service.py, Lines: ~718–755\n\n## Recommendation\nRemove `recommend_bid` and `recommend_nomination`.\n\n## Acceptance Criteria\n- [ ] `recommend_bid` and `recommend_nomination` module-level functions are removed\n- [ ] `__init__.py` exports are unchanged",
        "labels": ["enhancement", "code-review", "services", "priority:P3"],
    },
    {
        "title": "[IMPROVEMENT][P3] services/draft_loading_service.py: inline __import__('os') when os is already imported at module level",
        "body": "## Problem\nInside `_load_fantasypros_draft`:\n```python\nif not data_path or not __import__('os').path.isdir(data_path):\n```\n`os` is already imported at the top of the file. Using `__import__('os')` is unidiomatic Python and misleads readers.\n\n## Location\nFile: services/draft_loading_service.py, Line(s): ~122\n\n## Recommendation\n```python\nif not data_path or not os.path.isdir(data_path):\n```\n\n## Acceptance Criteria\n- [ ] No `__import__('os')` calls remain in this file",
        "labels": ["enhancement", "code-review", "services", "priority:P3"],
    },

    # ── STRATEGIES MODULE ───────────────────────────────────────────────────
    {
        "title": "[BUG][P0] strategies/enhanced_vor_strategy.py: InflationAwareVorStrategy missing should_nominate → TypeError on instantiation",
        "body": "## Problem\n`InflationAwareVorStrategy` extends `Strategy`, which declares `should_nominate` as `@abstractmethod`. The class never defines `should_nominate`, so Python's ABC machinery raises `TypeError: Can't instantiate abstract class InflationAwareVorStrategy with abstract method should_nominate` the moment anyone calls `InflationAwareVorStrategy()`.\n\n## Location\nFile: strategies/enhanced_vor_strategy.py (class body; `should_nominate` never defined)\n\n## Recommendation\nAdd a concrete `should_nominate` implementation:\n```python\ndef should_nominate(self, player, team, owner, available_players):\n    # VOR-aware: prefer players with highest VOR to force bidding on valuable targets\n    return player.vor > 0\n```\n\n## Acceptance Criteria\n- [ ] `InflationAwareVorStrategy()` can be instantiated without raising `TypeError`\n- [ ] `should_nominate` applies VOR-aware nomination logic\n- [ ] Unit test added covering instantiation",
        "labels": ["bug", "code-review", "strategies", "priority:P0"],
    },
    {
        "title": "[BUG][P0] strategies/strategy_analyzer.py: Wrong import source — from classes import create_strategy raises ImportError",
        "body": "## Problem\n`strategy_analyzer.py` imports:\n```python\nfrom classes import create_strategy, AVAILABLE_STRATEGIES\n```\n`create_strategy` and `AVAILABLE_STRATEGIES` are defined in `strategies/__init__.py`, not `classes/__init__.py`. Running this script raises `ImportError: cannot import name 'create_strategy' from 'classes'`, making the entire analysis tool broken.\n\n## Location\nFile: strategies/strategy_analyzer.py, Lines: 8–9\n\n## Recommendation\n```python\nfrom strategies import create_strategy, AVAILABLE_STRATEGIES\n```\n\n## Acceptance Criteria\n- [ ] `python strategies/strategy_analyzer.py` runs without `ImportError`\n- [ ] `test_strategy_bidding()` iterates all strategies and prints bid results",
        "labels": ["bug", "code-review", "strategies", "priority:P0"],
    },
    {
        "title": "[BUG][P1] strategies/adaptive_strategy.py + aggressive_strategy.py: Dead branch position_priority >= 2.0 — mandatory K/DST bid logic never fires",
        "body": "## Problem\nBoth `adaptive_strategy.py` and `aggressive_strategy.py` contain:\n```python\nif position_priority >= 2.0 and player.position in ['K', 'DST']:\n    # We MUST have these positions — bid aggressively\n```\n`_calculate_position_priority` is capped at `min(1.0, ...)` by definition. The condition `>= 2.0` is therefore unreachable dead code. The special K/DST mandatory-bid branch **never** executes, so teams can fail to fill K/DST roster slots.\n\n## Location\nFile: strategies/adaptive_strategy.py, Lines: ~59–62\nFile: strategies/aggressive_strategy.py, Lines: ~43–46\n\n## Recommendation\nReplace `position_priority >= 2.0` with `position_priority >= 0.9`.\n\n## Acceptance Criteria\n- [ ] K/DST mandatory bid branch is reachable and covered by a unit test\n- [ ] Strategies nominate K/DST players when roster slots remain unfilled",
        "labels": ["bug", "code-review", "strategies", "priority:P1"],
    },
    {
        "title": "[BUG][P1] strategies/base_strategy.py: __init_subclass__ wrapper drops **kwargs — InflationAwareVorStrategy inflation parameter silently ignored",
        "body": "## Problem\nThe `__init_subclass__` metaclass wrapper replaces every subclass `calculate_bid` with a wrapper that only passes six positional args to the original. `InflationAwareVorStrategy.calculate_bid` accepts `**kwargs` and uses `kwargs.get('all_teams', [team])` to compute market inflation. The wrapper calls the original with only the six positional args, **silently discarding all keyword arguments**. Any caller passing `all_teams=[...]` will never have that value reach the inflation calculation.\n\n## Location\nFile: strategies/base_strategy.py, Lines: ~53–62 (`_wrapped_calculate_bid`)\n\n## Recommendation\nForward `**kwargs` through the wrapper:\n```python\ndef _wrapped_calculate_bid(self, player, team, owner, current_bid, remaining_budget, remaining_players, *args, _f=_orig_calc, **kwargs):\n    raw = _f(self, player, team, owner, current_bid, remaining_budget, remaining_players, **kwargs)\n```\n\n## Acceptance Criteria\n- [ ] Passing `all_teams=[...]` to `InflationAwareVorStrategy.calculate_bid` reaches `_calculate_inflation_factor`\n- [ ] Existing tests for wrapped strategies still pass",
        "labels": ["bug", "code-review", "strategies", "priority:P1"],
    },
    {
        "title": "[BUG][P1] strategies/aggressive_strategy.py: team.initial_budget accessed without guard — AttributeError or ZeroDivisionError at runtime",
        "body": "## Problem\n`AggressiveStrategy.calculate_bid` computes `budget_ratio = remaining_budget / team.initial_budget` with no `hasattr` check or try/except. Two failure modes: (1) `AttributeError` if `team` doesn't expose `initial_budget`, (2) `ZeroDivisionError` if `team.initial_budget == 0`.\n\n## Location\nFile: strategies/aggressive_strategy.py, Line(s): ~55\n\n## Recommendation\n```python\ninitial_budget = getattr(team, 'initial_budget', None) or 200.0\nbudget_ratio = remaining_budget / initial_budget\n```\n\n## Acceptance Criteria\n- [ ] No `AttributeError` when `team.initial_budget` is absent\n- [ ] No `ZeroDivisionError` when `team.initial_budget == 0`\n- [ ] Unit test covers both edge cases",
        "labels": ["bug", "code-review", "strategies", "priority:P1"],
    },
    {
        "title": "[BUG][P1] strategies/sigmoid_strategy.py: Multiple unguarded team/owner attribute accesses — AttributeError crashes auction",
        "body": "## Problem\n`SigmoidStrategy` directly accesses several attributes that may not exist on all `Team`/`Owner` implementations without guarding:\n\n| Location | Access | Failure |\n|---|---|---|\n| `_calculate_budget_pressure` | `team.initial_budget` | AttributeError / ZeroDivisionError |\n| `_calculate_budget_pressure` | `team.roster_requirements` | AttributeError |\n| `calculate_bid` | `team.roster_config.values()` | AttributeError |\n| `should_nominate` | `owner.is_target_player(player.player_id)` | AttributeError |\n| `calculate_bid` | `player.auction_value` (no fallback) | AttributeError |\n\n## Location\nFile: strategies/sigmoid_strategy.py, Lines: ~72–75, ~101, ~133, ~163\n\n## Recommendation\nApply `getattr(..., fallback)` for each access, consistent with how `value_based_strategy.py` uses `_get_player_value` and optional chaining.\n\n## Acceptance Criteria\n- [ ] `SigmoidStrategy` operates correctly with teams that lack `initial_budget`, `roster_requirements`, or `roster_config`\n- [ ] `should_nominate` catches `AttributeError` from `owner.is_target_player`",
        "labels": ["bug", "code-review", "strategies", "priority:P1"],
    },
    {
        "title": "[BUG][P1] strategies/vor_strategy.py: Local variable vor_scaling_factor shadows self._vor_scaling_factor — subclass overrides ignored",
        "body": "## Problem\n`VorStrategy.__init__` computes and stores `self._vor_scaling_factor`. However, `calculate_bid` ignores this field and hard-codes a local variable:\n```python\nvor_scaling_factor = 0.25  # Increased from 0.15 to 0.25 per VOR point\nbase_bid = vor * vor_scaling_factor * ...\n```\nAny subclass that overrides `_calculate_vor_scaling_factor` to return a custom value will have its override silently discarded. `self._vor_scaling_factor` is a dead field.\n\n## Location\nFile: strategies/vor_strategy.py, Lines: ~144–145\n\n## Recommendation\n```python\nbase_bid = vor * self._vor_scaling_factor * scarcity_adjustment\n```\n\n## Acceptance Criteria\n- [ ] `VorStrategy.calculate_bid` uses `self._vor_scaling_factor`\n- [ ] Subclasses overriding `_calculate_vor_scaling_factor` see their value reflected in bids",
        "labels": ["bug", "code-review", "strategies", "priority:P1"],
    },
    {
        "title": "[BUG][P2] strategies/balanced_strategy.py: VOR computed in auction dollars with flat $5 baseline — not true VOR",
        "body": "## Problem\n`BalancedStrategy.calculate_bid` computes:\n```python\nbaseline_value = 5  # Minimum replacement level value\nvor = max(0, player_value - baseline_value)\n```\nwhere `player_value` is the player's **auction dollar value**. This is not Value Over Replacement — it is simply `auction_value - $5`. True VOR is computed in fantasy points relative to a position-specific replacement level. The `vor_variance` parameter claims to apply VOR-based variance but actually applies auction-price variance.\n\n## Location\nFile: strategies/balanced_strategy.py, Lines: ~85–92\n\n## Recommendation\nEither (a) rename variables to reflect what they actually compute, or (b) implement proper position-specific replacement levels in fantasy points matching `vor_strategy.py`'s approach.\n\n## Acceptance Criteria\n- [ ] Variable naming accurately reflects what is computed\n- [ ] OR: position-specific baselines used so K/DST, QB, RB comparisons are meaningful",
        "labels": ["bug", "code-review", "strategies", "priority:P2"],
    },
    {
        "title": "[BUG][P2] strategies/base_strategy.py: calculate_max_bid returns 1 when max_bid < 0, allowing over-budget bids",
        "body": "## Problem\n`calculate_max_bid` returns 1 when `max_bid < 0` but `remaining_budget > 0`:\n```python\nif max_bid < 1 and remaining_budget > 0:\n    return 1  # Allow teams to bid $1 even if slightly short\n```\nWhen `remaining_budget < min_budget_needed`, the team literally does not have enough money to both win this bid and reserve $1 for every remaining roster slot. Returning 1 pushes the team past the budget floor. The gap can be arbitrarily large, not \"slightly short\".\n\n## Location\nFile: strategies/base_strategy.py, Lines: ~218–222\n\n## Recommendation\n```python\nif max_bid < 1 and remaining_budget > 0:\n    if remaining_budget >= min_budget_needed - 1:\n        return 1\n    return 0\n```\n\n## Acceptance Criteria\n- [ ] When `remaining_budget < min_budget_needed - 1`, `calculate_max_bid` returns 0\n- [ ] Budget constraint integration tests confirm no over-budget final rosters",
        "labels": ["bug", "code-review", "strategies", "priority:P2"],
    },
    {
        "title": "[IMPROVEMENT][P2] strategies/__init__.py: SmartStrategy in AVAILABLE_STRATEGIES but commented out of __all__ — inconsistent public API",
        "body": "## Problem\n`AVAILABLE_STRATEGIES` includes `'smart': SmartStrategy`, meaning `create_strategy('smart')` works and the strategy participates in tournaments. However `__all__` has `# 'SmartStrategy',` commented out. This inconsistency means IDEs and `help(strategies)` do not list `SmartStrategy` as a public symbol, confusing contributors.\n\n## Location\nFile: strategies/__init__.py, Lines: ~34, ~79\n\n## Recommendation\nDecide the authoritative state: if production-ready, add to `__all__`. If a placeholder, remove from `AVAILABLE_STRATEGIES`.\n\n## Acceptance Criteria\n- [ ] `SmartStrategy` is either in both `AVAILABLE_STRATEGIES` and `__all__`, or in neither",
        "labels": ["enhancement", "code-review", "strategies", "priority:P2"],
    },
    {
        "title": "[IMPROVEMENT][P2] strategies/enhanced_vor_strategy.py: InflationAwareVorStrategy not registered in AVAILABLE_STRATEGIES — class is unreachable",
        "body": "## Problem\n`InflationAwareVorStrategy` is defined but: (1) never imported in `strategies/__init__.py`, (2) not added to `AVAILABLE_STRATEGIES`, (3) cannot be created via `create_strategy`. The file also contains a stub `test_inflation_aware_strategy()` that does nothing.\n\n## Location\nFile: strategies/__init__.py (missing import)\nFile: strategies/enhanced_vor_strategy.py (entire class)\n\n## Recommendation\n1. Fix the P0 `should_nominate` bug first.\n2. Add to `strategies/__init__.py`: `from .enhanced_vor_strategy import InflationAwareVorStrategy` and add `'inflation_vor': InflationAwareVorStrategy` to `AVAILABLE_STRATEGIES`.\n3. Remove or implement the dead test stub.\n\n## Acceptance Criteria\n- [ ] `create_strategy('inflation_vor')` returns an `InflationAwareVorStrategy` instance\n- [ ] Dead test stub removed or replaced with a real test",
        "labels": ["enhancement", "code-review", "strategies", "priority:P2"],
    },
    {
        "title": "[IMPROVEMENT][P2] strategies/*: Hardcoded position_targets and total_slots = 15 duplicated across 10+ files",
        "body": "## Problem\nThe following dict is copy-pasted with minor variations into at least 10 strategy files:\n```python\nposition_targets = {'QB': 2, 'RB': 4, 'WR': 4, 'TE': 2, 'K': 1, 'DST': 1}\ntotal_slots = 15\n```\nThe base class already implements `_calculate_position_priority` and `_get_remaining_roster_slots` with proper fallback to `team.roster_config`. Overriding these with hardcoded values means non-standard leagues (SuperFlex, 2QB, dynasty) silently use the wrong slot count.\n\n## Location\nFiles: strategies/balanced_strategy.py, basic_strategy.py, elite_hybrid_strategy.py, hybrid_strategies.py, improved_value_strategy.py, random_strategy.py, refined_value_random_strategy.py, league_strategy.py\n\n## Recommendation\nRemove the `_calculate_position_priority` and `_get_remaining_roster_slots` overrides from all strategies that only replicate the base logic. Let all strategies inherit the base implementation which reads from `team.roster_config`.\n\n## Acceptance Criteria\n- [ ] At most one canonical `_calculate_position_priority` implementation per strategy\n- [ ] Strategies that hardcoded `total_slots = 15` now use the base class implementation\n- [ ] Tests verify correct behavior with a non-standard 16-slot roster config",
        "labels": ["enhancement", "code-review", "strategies", "tech-debt", "priority:P2"],
    },
    {
        "title": "[IMPROVEMENT][P2] strategies/enhanced_vor_strategy.py: Hardcoded standard_budget_per_slot = 200 / 15 breaks non-standard leagues",
        "body": "## Problem\n`InflationAwareVorStrategy._calculate_inflation_factor` hardcodes `standard_budget_per_slot = 200 / 15 (~$13.33)`. In leagues with $100 budget, inflation is massively overstated. The values `200` and `15` also appear in `spending_analyzer.py`, creating three separate places where the same defaults live.\n\n## Location\nFile: strategies/enhanced_vor_strategy.py, Lines: ~118–120\n\n## Recommendation\nDerive from the teams themselves:\n```python\nstandard_budget = getattr(all_teams[0], 'initial_budget', 200) if all_teams else 200\nstandard_slots = 15  # or read from config\nstandard_budget_per_slot = standard_budget / standard_slots\n```\n\n## Acceptance Criteria\n- [ ] `_calculate_inflation_factor` computes neutral inflation (returns 1.0) for a default 12-team $200 league\n- [ ] Inflation factor is accurate for a $100-budget league\n- [ ] No hardcoded `200 / 15` magic number remains",
        "labels": ["enhancement", "code-review", "strategies", "priority:P2"],
    },
    {
        "title": "[IMPROVEMENT][P3] strategies/adaptive_strategy.py: bid_history grows unboundedly — memory leak in multi-round tournament simulations",
        "body": "## Problem\n`self.bid_history = []` grows without bound as `update_draft_trends` appends every `(player, winning_bid)` tuple. There is no maximum length cap. In multi-round tournament simulations where the same strategy instance is reused, `bid_history` accumulates all historical bids indefinitely. `_update_aggression` already slices to `self.bid_history[-10:]` for computation, so only the last 10 items are ever used — the full history is retained for no purpose.\n\n## Location\nFile: strategies/adaptive_strategy.py, Lines: ~33 (`bid_history = []`), ~155 (`self.bid_history.append(...)`)\n\n## Recommendation\n```python\nfrom collections import deque\nself.bid_history: deque = deque(maxlen=10)\n```\n\n## Acceptance Criteria\n- [ ] `bid_history` is a `deque(maxlen=10)` or equivalent bounded container\n- [ ] Memory usage stays constant across 1000-round simulation\n- [ ] `_update_aggression` produces identical results before and after the change",
        "labels": ["enhancement", "code-review", "strategies", "priority:P3"],
    },
    {
        "title": "[IMPROVEMENT][P3] strategies/spending_analyzer.py: Stale hardcoded tournament data + wrong module location",
        "body": "## Problem\n`spending_analyzer.py` contains two issues:\n1. `spending_data` is a static dict with hardcoded tournament results. As strategies evolve, these numbers become wrong with no indication of staleness.\n2. This is a standalone analysis script (has `if __name__ == '__main__'`), not a strategy class. Placing it in `strategies/` pollutes the module namespace and it is excluded from `__all__`.\n\n## Location\nFile: strategies/spending_analyzer.py\n\n## Recommendation\n- Move to `scripts/spending_analyzer.py` or `utils/spending_analyzer.py`.\n- Replace hardcoded data with a call to `TournamentService.run_tournament(...)` or document the data with a timestamp.\n\n## Acceptance Criteria\n- [ ] `spending_analyzer.py` removed from `strategies/` module\n- [ ] File moved to an appropriate location outside the `strategies/` package",
        "labels": ["enhancement", "code-review", "strategies", "priority:P3"],
    },

    # ── CLI / CONFIG / DATA / UTILS ─────────────────────────────────────────
    {
        "title": "[BUG][P1] cli/commands.py: Dead unreachable code block after return in _run_elimination_rounds",
        "body": "## Problem\nAt line 272, `_run_elimination_rounds` returns `{'success': True, ...}` and then immediately continues with a large block of code (lines 273–302) that begins with a docstring and executable statements. This code is entirely unreachable — Python will never execute it. The comprehensive tournament logic is silently lost. This appears to be code that was meant to live in a separate method body but was pasted inside `_run_elimination_rounds` by mistake.\n\n## Location\nFile: cli/commands.py, Lines: 272–302\n\n## Recommendation\nExtract the dead block into its own method (e.g., `_run_comprehensive_tournament_with_timing`) or delete it if it is intentionally replaced.\n\n## Acceptance Criteria\n- [ ] Unreachable code block removed from `_run_elimination_rounds`\n- [ ] If the logic was intended, it is reachable via the correct method dispatch",
        "labels": ["bug", "code-review", "cli", "priority:P1"],
    },
    {
        "title": "[BUG][P1] utils/path_utils.py: get_data_file doubles the data/ path segment",
        "body": "## Problem\n`get_data_dir()` already returns `<project_root>/data`. `get_data_file(filename)` then appends `/ \"data\" / filename`, producing `<project_root>/data/data/<filename>`. The directory `data/data/` does not exist, so every caller receives a path that will never resolve to a real file.\n\n## Location\nFile: utils/path_utils.py, Line: 40\n\n## Recommendation\n```python\ndef get_data_file(filename: str) -> Path:\n    return get_data_dir() / filename  # Remove extra \"data\" segment\n```\n\n## Acceptance Criteria\n- [ ] `get_data_file('sheets/QB.csv')` resolves to `<root>/data/sheets/QB.csv`\n- [ ] Unit test added asserting correct path construction",
        "labels": ["bug", "code-review", "utils", "priority:P1"],
    },
    {
        "title": "[BUG][P1] cli/main.py: handle_tournament_command crashes with unhandled ValueError on non-numeric args",
        "body": "## Problem\nLines 208–209 call `int(filtered_args[0])` and `int(filtered_args[1])` with no try/except. If a user passes `tournament abc`, Python raises an uncaught `ValueError` that propagates as a raw traceback instead of a helpful message.\n\n## Location\nFile: cli/main.py, Lines: 208–209\n\n## Recommendation\n```python\ntry:\n    rounds = int(filtered_args[0]) if filtered_args else 10\nexcept ValueError:\n    print(f\"ERROR: rounds must be an integer, got '{filtered_args[0]}'\")\n    return 1\n```\n\n## Acceptance Criteria\n- [ ] `tournament abc` prints a user-friendly error and returns exit code 1\n- [ ] Valid invocations are unaffected",
        "labels": ["bug", "code-review", "cli", "priority:P1"],
    },
    {
        "title": "[BUG][P1] cli/main.py: _display_ping_results raises KeyError if tests key is missing",
        "body": "## Problem\nLine 527 iterates `result['tests']` via direct dict access. If `test_sleeper_connectivity()` returns a result dict without the `'tests'` key (e.g., on an early error return), this raises an unhandled `KeyError`, crashing the ping command.\n\n## Location\nFile: cli/main.py, Line: 527\n\n## Recommendation\n```python\nfor test in result.get('tests', []):\n```\n\n## Acceptance Criteria\n- [ ] `ping` does not raise `KeyError` when `tests` is absent from the result\n- [ ] An appropriate fallback message is shown when no test results are available",
        "labels": ["bug", "code-review", "cli", "priority:P1"],
    },
    {
        "title": "[SECURITY][P1] utils/path_utils.py: No path traversal validation in get_data_file and safe_file_path",
        "body": "## Problem\nBoth `get_data_file(filename)` and `safe_file_path(path)` accept arbitrary strings without checking that the resolved path stays within the intended directory. If `filename` contains `../` sequences (e.g., `../../etc/passwd`), the resolved path escapes the project tree. `safe_file_path` calls `ensure_dir_exists(path.parent)`, which would create arbitrary directories for attacker-supplied paths.\n\n## Location\nFile: utils/path_utils.py, Lines: 39–49\n\n## Recommendation\nAdd canonicalization and boundary checks:\n```python\ndef get_data_file(filename: str) -> Path:\n    resolved = (get_data_dir() / filename).resolve()\n    if not str(resolved).startswith(str(get_data_dir().resolve())):\n        raise ValueError(f\"Path traversal detected: {filename}\")\n    return resolved\n```\n\n## Acceptance Criteria\n- [ ] `get_data_file('../../../etc/passwd')` raises `ValueError`\n- [ ] `safe_file_path` raises `ValueError` for paths outside the project root\n- [ ] Tests added covering traversal attempts",
        "labels": ["bug", "code-review", "utils", "security", "priority:P1"],
    },
    {
        "title": "[BUG][P1] cli/commands.py: run_elimination_tournament uses hardcoded strategy list instead of AVAILABLE_STRATEGIES",
        "body": "## Problem\n`run_elimination_tournament` defines `all_strategies` as a hardcoded list of 16 strategy names. When strategies are added or removed from the codebase, this list silently diverges. New strategies are never tested in the tournament, and removed strategy keys cause runtime errors.\n\n## Location\nFile: cli/commands.py, Lines: 168–175\n\n## Recommendation\n```python\nall_strategies = list(AVAILABLE_STRATEGIES)\n```\nThis is already imported.\n\n## Acceptance Criteria\n- [ ] `run_elimination_tournament` uses `AVAILABLE_STRATEGIES` as the source of truth\n- [ ] Adding a new strategy automatically includes it in tournaments",
        "labels": ["bug", "code-review", "cli", "priority:P1"],
    },
    {
        "title": "[IMPROVEMENT][P2] config/settings.py: get_settings() re-reads .env on every call — missing lru_cache",
        "body": "## Problem\n`get_settings()` calls `Settings()` on every invocation. Since `pydantic-settings` `BaseSettings` reads and parses the `.env` file during `__init__`, every call triggers disk I/O. `get_settings()` is called inside `ConfigManager.load_config()`, which is called frequently across the request lifecycle.\n\n## Location\nFile: config/settings.py, Lines: 24–26\n\n## Recommendation\n```python\nfrom functools import lru_cache\n\n@lru_cache(maxsize=1)\ndef get_settings() -> Settings:\n    return Settings()\n```\n\n## Acceptance Criteria\n- [ ] `get_settings()` is decorated with `@lru_cache(maxsize=1)`\n- [ ] `Settings()` constructor is called at most once per process\n- [ ] Cache invalidation documented (`get_settings.cache_clear()` for tests)",
        "labels": ["enhancement", "code-review", "priority:P2"],
    },
    {
        "title": "[RELIABILITY][P2] config/config_manager.py: load_config misses PermissionError and OSError in exception handler",
        "body": "## Problem\nLine 95 catches `(json.JSONDecodeError, FileNotFoundError, KeyError)` but not `PermissionError` or `OSError`. If `config.json` exists but is not readable (wrong file permissions, NFS issue, etc.), the uncaught `PermissionError` propagates up and crashes the CLI with a raw traceback instead of a graceful fallback to defaults.\n\n## Location\nFile: config/config_manager.py, Line: 95\n\n## Recommendation\n```python\nexcept (json.JSONDecodeError, FileNotFoundError, KeyError, PermissionError, OSError) as e:\n    logger.error(\"Config file unreadable: %s\", e)\n    return DraftConfig()\n```\n\n## Acceptance Criteria\n- [ ] A config file with `chmod 000` causes a graceful fallback to defaults with a logged warning",
        "labels": ["bug", "code-review", "priority:P2"],
    },
    {
        "title": "[RELIABILITY][P2] config/config_manager.py: Settings layer exception silently swallowed — .env parse errors invisible",
        "body": "## Problem\nLines 100–107 wrap the pydantic-settings layer in `except Exception: pass`. If `settings.py` has a Pydantic validation error (e.g., `BUDGET=abc` in `.env`), the error is swallowed without any log output. The user sees default values applied with no indication that their `.env` configuration was ignored.\n\n## Location\nFile: config/config_manager.py, Lines: 100–107\n\n## Recommendation\nChange `except Exception: pass` to:\n```python\nexcept Exception as e:\n    logger.warning(\"Could not load env settings (using JSON config only): %s\", e)\n```\n\n## Acceptance Criteria\n- [ ] An invalid value in `.env` (e.g., `BUDGET=notanumber`) produces a `WARNING` log entry\n- [ ] The config manager still falls back to JSON-file values",
        "labels": ["bug", "code-review", "priority:P2"],
    },
    {
        "title": "[SECURITY][P2] data/fantasypros_loader.py: data_path passed to file I/O without validation or canonicalization",
        "body": "## Problem\n`FantasyProsLoader.__init__` accepts `data_path` directly from `config.data_path`, which is loaded from `config.json` (an externally editable file). The path is used verbatim in file I/O without resolving or validating that it points within the project. A malicious or misconfigured `config.json` (e.g., `\"data_path\": \"/etc\"`) would silently attempt to open system files. The default `\"data/sheets\"` is also a relative path that resolves against CWD.\n\n## Location\nFile: data/fantasypros_loader.py, Lines: 25–27, 53–54\n\n## Recommendation\n1. Resolve `data_path` relative to the project root at construction time.\n2. Validate that the resolved path is within `get_project_root()`.\n\n## Acceptance Criteria\n- [ ] `data_path` is always resolved to an absolute path at `__init__` time\n- [ ] Paths outside the project root raise `ValueError`\n- [ ] Running the CLI from any working directory produces the same file paths",
        "labels": ["bug", "code-review", "security", "priority:P2"],
    },
    {
        "title": "[PERFORMANCE][P2] data/fantasypros_loader.py: CSV files re-read from disk on every load_position_data call — no caching",
        "body": "## Problem\n`load_position_data(position)` opens and fully parses the CSV file on every invocation. There is no in-memory cache. `load_all_players()` calls `load_position_data` for every position on every draft, producing hundreds of redundant disk reads during a tournament run.\n\n## Location\nFile: data/fantasypros_loader.py, Lines: 43–78\n\n## Recommendation\nAdd an instance-level cache:\n```python\nself._cache: Dict[str, List[Player]] = {}\n\ndef load_position_data(self, position: str) -> List[Player]:\n    if position not in self._cache:\n        self._cache[position] = self._load_from_disk(position)\n    return self._cache[position]\n```\n\n## Acceptance Criteria\n- [ ] Each position CSV is read at most once per `FantasyProsLoader` instance\n- [ ] `clear_cache()` method resets the cache for test isolation",
        "labels": ["enhancement", "code-review", "priority:P2"],
    },
    {
        "title": "[BUG][P2] data/fantasypros_loader.py: calculate_auction_values hardcodes total_budget=2400.0 ignoring actual config",
        "body": "## Problem\n`calculate_auction_values` defaults `total_budget=2400.0`, which assumes 12 teams × $200. This value is never derived from the actual `DraftConfig.budget` or `DraftConfig.num_teams`. Leagues with different team counts or budgets receive systematically wrong auction values.\n\n## Location\nFile: data/fantasypros_loader.py, Lines: 196–200, ~230\n\n## Recommendation\nPass `num_teams` and `budget` from config when calling `calculate_auction_values`:\n```python\nself.calculate_auction_values(\n    all_players,\n    total_budget=config.budget * config.num_teams\n)\n```\n\n## Acceptance Criteria\n- [ ] `calculate_auction_values` uses the actual configured budget × num_teams\n- [ ] Unit test verifies auction values change with different config values",
        "labels": ["bug", "code-review", "priority:P2"],
    },
    {
        "title": "[RELIABILITY][P2] utils/cheatsheet_parser.py: Stub class silently returns empty results — no NotImplementedError",
        "body": "## Problem\n`CheatsheetParser.find_undervalued_players_simple`, `find_undervalued_players`, and `get_all_players` are stub implementations that return `[]`, `[]`, and `{}` respectively, with no indication to callers that the feature is unimplemented. Any code path that calls these methods will receive empty data and silently present \"no undervalued players found\" — a misleading result that looks like valid output.\n\n## Location\nFile: utils/cheatsheet_parser.py, Lines: 14–41\n\n## Recommendation\nRaise `NotImplementedError` in each stub method until real implementations are provided:\n```python\ndef find_undervalued_players(self, threshold: float = 10.0) -> List[Dict]:\n    raise NotImplementedError(\"CheatsheetParser.find_undervalued_players is not yet implemented\")\n```\n\n## Acceptance Criteria\n- [ ] Calling any stub method raises `NotImplementedError` with a descriptive message\n- [ ] CLI `undervalued` command surfaces the error to the user rather than showing empty results",
        "labels": ["bug", "code-review", "utils", "priority:P2"],
    },
    {
        "title": "[DESIGN][P2] utils/market_tracker.py: Module-level mutable singleton has no thread safety",
        "body": "## Problem\n`_market_tracker_instance` is a module-level global that is read and written via `get_market_tracker()` and `set_market_tracker()` without any locking. In any future context with concurrent draft sessions (async FastAPI endpoints, multi-threaded tournament runners), multiple threads could simultaneously call `set_market_tracker` and read stale or partially-initialized state.\n\n## Location\nFile: utils/market_tracker.py, Lines: 11–19\n\n## Recommendation\nProtect the singleton with a `threading.Lock`:\n```python\nimport threading\n_lock = threading.Lock()\n\ndef set_market_tracker(tracker) -> None:\n    global _market_tracker_instance\n    with _lock:\n        _market_tracker_instance = tracker\n```\n\n## Acceptance Criteria\n- [ ] `set_market_tracker` and `get_market_tracker` are protected by a lock\n- [ ] No global mutable state is accessed without synchronization",
        "labels": ["enhancement", "code-review", "utils", "priority:P2"],
    },
    {
        "title": "[PERFORMANCE][P2] utils/sleeper_cache.py: _get_cache_metadata reads metadata file from disk on every invocation",
        "body": "## Problem\n`_get_cache_metadata()` opens and parses `sleeper_players_meta.json` on every call. It is invoked multiple times in the normal `get_players()` path (once in `_is_cache_valid()`, once for logging, once in `get_cache_info()`). Each call is a redundant disk read.\n\n## Location\nFile: utils/sleeper_cache.py, Lines: 42–58\n\n## Recommendation\nCache the metadata dict in memory after the first read, and invalidate only after `_save_cache_metadata` is called:\n```python\nself._meta_cache: Optional[Dict] = None\n\ndef _get_cache_metadata(self) -> Dict:\n    if self._meta_cache is None:\n        self._meta_cache = self._read_meta_from_disk()\n    return self._meta_cache\n```\n\n## Acceptance Criteria\n- [ ] Metadata file is read at most once per `SleeperPlayerCache` instance unless invalidated by a write\n- [ ] `_save_cache_metadata` updates the in-memory cache",
        "labels": ["enhancement", "code-review", "utils", "priority:P2"],
    },
    {
        "title": "[MAINTAINABILITY][P2] cli/main.py: Hardcoded '2024' season default will silently query wrong year",
        "body": "## Problem\nLines 281 and 334 default the `season` parameter to the string `\"2024\"` in `handle_sleeper_status` and `handle_sleeper_leagues`. As of 2025+, this will silently query historical data rather than the current season with no mechanism for the user to discover this.\n\n## Location\nFile: cli/main.py, Lines: 281, 334\n\n## Recommendation\n```python\nimport datetime\ndefault_season = str(datetime.date.today().year)\nseason = args[1] if len(args) > 1 else default_season\n```\n\n## Acceptance Criteria\n- [ ] Default season is derived from the current year\n- [ ] Both `handle_sleeper_status` and `handle_sleeper_leagues` are updated",
        "labels": ["bug", "code-review", "cli", "priority:P2"],
    },
    {
        "title": "[DESIGN][P2] cli/main.py + cli/commands.py: Duplicate instantiation of ConfigManager and SleeperAPI",
        "body": "## Problem\n`AuctionDraftCLI.__init__` creates its own `ConfigManager()` and `SleeperAPI()` instances. `CommandProcessor.__init__` independently creates another `ConfigManager()` and `SleeperAPI()`. The two `ConfigManager` instances hold separate `_config` caches — if one updates the config, the other remains stale. Unnecessary resource duplication.\n\n## Location\nFile: cli/main.py, Lines: 55–57\nFile: cli/commands.py, Lines: 22–24\n\n## Recommendation\nUse the module-level `get_config_manager()` singleton and pass a single `ConfigManager` instance into `CommandProcessor` at construction:\n```python\nclass AuctionDraftCLI:\n    def __init__(self):\n        self.config_manager = get_config_manager()\n        self.command_processor = CommandProcessor(config_manager=self.config_manager)\n```\n\n## Acceptance Criteria\n- [ ] Only one `ConfigManager` instance exists per process\n- [ ] Config updates made through one reference are visible to all callers",
        "labels": ["enhancement", "code-review", "cli", "tech-debt", "priority:P2"],
    },
    {
        "title": "[MAINTAINABILITY][P3] cli/main.py: handle_undervalued_command is defined but never reachable via run()",
        "body": "## Problem\n`AuctionDraftCLI.handle_undervalued_command` is defined but is never registered in the `run()` dispatch table. The `undervalued` command cannot be invoked by any user. This is dead code that misleads readers into thinking the feature is available.\n\n## Location\nFile: cli/main.py (end of file)\n\n## Recommendation\nEither: (1) Add `elif command == 'undervalued': return self.handle_undervalued_command(args[1:])` to `run()` and add documentation in `show_help()`, or (2) Delete `handle_undervalued_command` and track the feature as a backlog item.\n\n## Acceptance Criteria\n- [ ] No unreachable command handlers exist in `AuctionDraftCLI`\n- [ ] If the command is intended, it appears in `run()` dispatch and `show_help()` output",
        "labels": ["enhancement", "code-review", "cli", "priority:P3"],
    },
]


def create_issue(issue: dict) -> tuple[bool, str]:
    labels = ",".join(issue["labels"])
    cmd = [
        "gh", "issue", "create",
        "--repo", "TylerJWhit/pigskin",
        "--title", issue["title"],
        "--body", issue["body"],
        "--label", labels,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        url = result.stdout.strip()
        return True, url
    else:
        return False, result.stderr.strip()


def main():
    print(f"Creating {len(ISSUES)} code review issues...")
    created = 0
    failed = 0

    for i, issue in enumerate(ISSUES, 1):
        print(f"[{i:>2}/{len(ISSUES)}] {issue['title'][:80]}...", end=" ", flush=True)
        ok, info = create_issue(issue)
        if ok:
            print(f"✓ {info}")
            created += 1
        else:
            print(f"✗ FAILED: {info}")
            failed += 1
        # Be gentle on the API
        time.sleep(0.5)

    print(f"\n{'='*60}")
    print(f"Done: {created} created, {failed} failed out of {len(ISSUES)} total")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
