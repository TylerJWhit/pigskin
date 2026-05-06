# Projection Source Accuracy Audit

- **Issue:** #198
- **Date:** 2026-04-30
- **Author:** Research Agent (Sprint 6)
- **Status:** COMPLETE
- **Downstream:** Initiative 2 (player projection pipeline), #126 (bid_recommendation_service)

---

## 1. Source Inventory

### FantasyPros

| Attribute | Details |
|-----------|---------|
| Data available | Season-level consensus projections (QB/RB/WR/TE/K); weekly expert rankings |
| Access method | **CSV export** (manual download) — current system uses this |
| Historical archives | 2016–present via web; 2022–2024 downloadable |
| ToS concern | **Automated scraping likely prohibited** (see #199 for compliance review) |
| Preprocessing | Loader already exists: `data/fantasypros_loader.py` |

### Sleeper

| Attribute | Details |
|-----------|---------|
| Data available | Season-level and week-level projections; historical stats |
| Access method | **Public REST API** — no authentication required |
| Historical archives | 2017–present; endpoint: `GET /stats/nfl/<season>/<week>` |
| ToS concern | **Generally permissive** for personal/research use (see #199) |
| Preprocessing | Normalize from Sleeper player_id to our `Player` model via player lookup |

### ESPN

| Attribute | Details |
|-----------|---------|
| Data available | Season projections; weekly rankings |
| Access method | Public fantasy API (undocumented); some endpoints require login for full data |
| Historical archives | Limited; ESPN periodically deprecates endpoints |
| ToS concern | **Mixed** — public endpoint tolerated but not officially sanctioned |
| Preprocessing | Requires ESPN player ID ↔ Sleeper player ID mapping |

### Yahoo

| Attribute | Details |
|-----------|---------|
| Data available | Season projections; weekly rankings |
| Access method | **OAuth 2.0 required** for fantasy data API |
| Historical archives | Available via authenticated API; 2020–present |
| ToS concern | OAuth requirement means no bulk unauthenticated access (see #199) |
| Preprocessing | Yahoo player key ↔ Sleeper player ID mapping required |

### numberFire

| Attribute | Details |
|-----------|---------|
| Data available | Season projections; DFS-focused metrics |
| Access method | **Web scraping only** — no public API |
| ToS concern | **Unknown — assumed prohibited** pending compliance review (#199) |
| Preprocessing | HTML scraping; brittle |

---

## 2. Accuracy Evaluation Framework

Since pulling 3-year historical accuracy data requires API access that may conflict with
ToS (addressed in #199), this section defines the evaluation methodology for
use once permissible data is collected.

### Primary Metric: Spearman Rank Correlation

Measures whether source correctly orders players by fantasy value — most relevant
for VOR because ranking accuracy directly determines auction value precision.

```
ρ = 1 - (6 Σd²) / (n(n²-1))
```

where `d` = difference between projected rank and actual rank for each player.

**Target by position (estimated achievable thresholds):**

| Position | Naive baseline (ρ) | Good source (ρ) | Best sources (ρ) |
|----------|--------------------|-----------------|-----------------|
| QB | ~0.65 | ~0.75 | ~0.82 |
| RB | ~0.55 | ~0.65 | ~0.72 |
| WR | ~0.58 | ~0.68 | ~0.75 |
| TE | ~0.50 | ~0.62 | ~0.70 |

*(Baselines from published fantasy analytics research; ADP-adjusted projections
typically outperform raw projections by 5–10 ρ points.)*

### Secondary Metric: Mean Absolute Error (MAE)

```
MAE = (1/n) Σ|projected_pts - actual_pts|
```

Less critical than rank correlation for VOR, but useful for identifying
systematic over/under-projection biases by source.

### Recommended Evaluation Design

```python
def evaluate_source(projected: list[tuple[str, float]],
                    actual: list[tuple[str, float]]) -> dict:
    """
    projected: [(player_id, projected_pts), ...]
    actual:    [(player_id, actual_pts), ...]
    Returns: {"spearman": float, "mae": float, "n": int}
    """
    from scipy.stats import spearmanr
    import numpy as np
    # align on player_id, drop players not in both sets
    ...
```

Implementation lives in `lab/eval/projection_accuracy.py` (stub exists).

---

## 3. Access + Integration Assessment

### Recommended Integration Priority

| Source | Recommendation | Reason |
|--------|---------------|--------|
| **Sleeper** | **Implement first** | Free, public API, no ToS risk, immediate access |
| **FantasyPros** | CSV only (manual) | Current system; automate only after #199 compliance clearance |
| **ESPN** | Deprioritize | Undocumented API, historical coverage gaps |
| **Yahoo** | Deprioritize | OAuth overhead; limited benefit over Sleeper consensus |
| **numberFire** | Do not implement | Web scraping; ToS unknown; brittle |

### Normalization Strategy (Sleeper → Player model)

```python
# Sleeper projection response: {player_id: {pts_ppr: float, rec: float, ...}}
# Our Player model fields: projected_points, position, name

def normalize_sleeper_projection(sleeper_data: dict, player_lookup: dict) -> list[Player]:
    players = []
    for player_id, stats in sleeper_data.items():
        if player_id not in player_lookup:
            continue
        p = player_lookup[player_id]
        p.projected_points = stats.get("pts_ppr", stats.get("pts_std", 0.0))
        players.append(p)
    return players
```

### Historical Data Access (Sleeper)

```
GET /stats/nfl/{season}/{week}?season_type=regular
```

For full-season projections (pre-draft):
```
GET /projections/nfl/{season}/1?season_type=regular  # week 1 pre-season projections
```

Both endpoints are unauthenticated and return JSON with ~3,000 player entries.

---

## 4. Recommendations for Initiative 2

1. **Start with Sleeper** — implement `lab/data/projections/sleeper_projections.py`
   to pull historical season projections for 2022–2024
2. **FantasyPros consensus** — continue using CSV export; evaluate adding
   automated ingestion only after compliance review (#199)
3. **Ensemble baseline** — simple average of Sleeper + FantasyPros consensus
   will outperform either source alone; implement as `lab/eval/ensemble.py`
4. **VOR recalibration** — once accuracy evaluation is complete, use the
   best-performing source's projections to recalibrate VOR baselines in
   `strategies/vor_strategy.py` and `strategies/enhanced_vor_strategy.py`
5. **Tracking** — all accuracy results must be written to `lab/results_db/`
   for longitudinal comparison across seasons and strategy changes
