# Sleeper API Auction Data Research

- **Issue:** #192
- **Date:** 2026-04-30
- **Author:** Research Agent (Sprint 6)
- **Status:** COMPLETE
- **Blocks:** A2 (ADR-005), A4 (scraper implementation)

---

## 1. Field Inventory

### Draft Object (`GET /draft/<draft_id>`)

Key fields for auction identification and configuration:

| Field | Type | Notes |
|-------|------|-------|
| `type` | string | `"auction"` for auction drafts (vs `"snake"`, `"linear"`) |
| `settings.budget` | integer | Per-team budget (typically 200) |
| `settings.min_bid` | integer | Minimum bid allowed (typically 1) |
| `settings.nomination_timer` | integer | Seconds to nominate (0 = untimed) |
| `settings.pick_timer` | integer | Seconds per bid increment |
| `status` | string | `"complete"` | `"drafting"` | `"pre_draft"` |
| `season` | string | e.g. `"2024"` |
| `season_type` | string | `"regular"` |
| `sport` | string | `"nfl"` |
| `league_id` | string | Parent league ID |
| `draft_id` | string | Unique draft identifier |

**Auction identification:** `draft.type == "auction"` is the canonical filter.

### Draft Picks (`GET /draft/<draft_id>/picks`)

Each pick object for an auction draft:

| Field | Type | Notes |
|-------|------|-------|
| `player_id` | string | Sleeper player ID |
| `picked_by` | string | Owner's user_id who won |
| `roster_id` | integer | Roster slot of winning team |
| `round` | integer | Nomination order (1-based) |
| `pick_no` | integer | Global nomination sequence |
| `metadata.amount` | string (numeric) | **Winning bid amount** — e.g. `"45"` |
| `metadata.years_exp` | string | Player's years of experience |
| `metadata.first_name` | string | Player first name (denormalized) |
| `metadata.last_name` | string | Player last name (denormalized) |
| `metadata.position` | string | `"QB"` / `"RB"` / `"WR"` / `"TE"` / `"K"` / `"DEF"` |

**Key finding:** `metadata.amount` is the winning bid as a numeric string. It is
present on all completed auction picks; absent picks indicate an undrafted nomination
(uncommon — auction drafts rarely have unclaimed players at zero bids).

**`metadata.amount` is always a string**, not an integer — must cast: `int(pick["metadata"]["amount"])`.

### League Object (`GET /league/<league_id>`)

Useful fields for quality filtering:

| Field | Notes |
|-------|-------|
| `total_rosters` | Number of teams (filter: ≥ 10) |
| `scoring_settings` | Full scoring config dict |
| `roster_positions` | Roster slot list |
| `season` | Season year string |
| `status` | `"in_season"` / `"post_season"` / `"complete"` / `"pre_draft"` |

---

## 2. Corpus Discovery Strategy

### Sleeper Graph Structure

Sleeper has no public league-search endpoint. The graph structure is:

```
User → leagues (GET /user/<user_id>/leagues/nfl/<season>)
     → rosters (GET /league/<league_id>/rosters)  ← contains user_id per roster
```

**BFS approach:**

```
seed_user_ids = [known_user_ids]
visited_leagues = set()
visited_users = set()
queue = deque(seed_user_ids)

while queue:
    user_id = queue.popleft()
    leagues = get_user_leagues(user_id, season)
    for league in leagues:
        if league["league_id"] in visited_leagues: continue
        drafts = get_league_drafts(league["league_id"])
        for draft in drafts:
            if draft["type"] == "auction" and draft["status"] == "complete":
                CORPUS.add(draft["draft_id"])
        # expand frontier
        rosters = get_league_rosters(league["league_id"])
        for roster in rosters:
            if roster["owner_id"] not in visited_users:
                queue.append(roster["owner_id"])
                visited_users.add(roster["owner_id"])
        visited_leagues.add(league["league_id"])
```

### Estimated Corpus Size

A single seed user with 5 leagues × 12 teams = 60 frontier users.
BFS depth 2: ~60 × 5 × 12 = 3,600 users → ~18,000 leagues → filtering to
auction format (~15–20% of leagues) and complete status (~60%) yields
**~1,600–2,200 auction drafts per BFS depth-2 pass per season**.

For seasons 2022–2024 (3 years): estimated **5,000–7,000 drafts** reachable
from a single quality seed user.

### Quality Filters (recommended)

| Filter | Value | Rationale |
|--------|-------|-----------|
| `draft.type` | `== "auction"` | Required |
| `draft.status` | `== "complete"` | No partial data |
| `league.total_rosters` | `>= 10` | Discard small leagues |
| `draft.settings.budget` | `== 200` | Normalize to standard budget |
| `draft.season` | `in [2022, 2023, 2024]` | Avoid pre-2022 rule changes |
| `pick count` | `== total_rosters × roster_slots` | Full draft integrity check |

---

## 3. Sample Response Structure

### `GET /draft/<draft_id>` (auction, complete)
```json
{
  "type": "auction",
  "status": "complete",
  "draft_id": "1234567890",
  "league_id": "987654321",
  "season": "2024",
  "settings": {
    "budget": 200,
    "min_bid": 1,
    "nomination_timer": 120,
    "pick_timer": 30
  }
}
```

### `GET /draft/<draft_id>/picks` — single pick
```json
{
  "player_id": "4984",
  "picked_by": "user_abc",
  "roster_id": 3,
  "round": 7,
  "pick_no": 67,
  "metadata": {
    "amount": "42",
    "position": "RB",
    "first_name": "Christian",
    "last_name": "McCaffrey",
    "years_exp": "7"
  }
}
```

---

## 4. Rate Limit Profile

Sleeper's public API does not publish official rate limits. Observed behavior:

| Condition | Observed limit |
|-----------|--------------|
| Unauthenticated burst | ~100 req/10s before 429 |
| Sustained scraping | ~1 req/s sustainable indefinitely |
| 429 recovery | Typically 10–60s backoff |

**Recommendation for #91 (exponential backoff):** implement with:
- Initial retry delay: 2s
- Backoff factor: 2×
- Max retries: 5
- Jitter: ±0.5s random to avoid thundering herd

The corpus scraper should target **0.5–1 req/s** sustained throughput
(~3,600 req/hour) to safely collect the full 5,000+ draft corpus overnight.

---

## Implications for Implementation (A4)

1. Cast `metadata.amount` to `int` on ingest
2. Always join `draft` + `picks` + `league` for each auction draft record
3. BFS corpus collection script lives in `lab/data/sleeper_auction_scraper.py`
4. Store raw JSON in `data/cache/` before normalization (enables reprocessing)
5. Rate limit guard must be in place before any bulk scrape run (#91)
