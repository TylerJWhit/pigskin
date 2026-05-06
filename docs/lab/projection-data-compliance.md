# Projection Data Compliance Memo

- **Issue:** #199
- **Date:** 2026-04-30
- **Author:** Compliance Agent (Sprint 6)
- **Status:** COMPLETE
- **Blocks:** #202 (projection ingestion pipeline — B4)

> **IMPORTANT:** This memo represents a good-faith research analysis of publicly
> available ToS information as of 2026-04-30. It is not legal advice. For any
> commercial use, consult a qualified attorney.

---

## Summary Verdict

| Source | Automated Collection | Recommended Method | Attribution Required |
|--------|---------------------|-------------------|---------------------|
| **Sleeper** | ✅ Permitted | Public REST API | No (encouraged) |
| **FantasyPros** | ⚠️ CSV only | Manual CSV export | Yes (per ToS) |
| **ESPN** | ❌ Not recommended | N/A | — |
| **Yahoo** | ⚠️ OAuth required | Yahoo Fantasy API (authenticated) | Yes |
| **numberFire** | ❌ Blocked | N/A | — |

---

## Source-by-Source Analysis

### Sleeper

**ToS summary:** Sleeper's developer documentation explicitly supports third-party
application development against their public API. The API is unauthenticated for
read-only operations and intended for open use.

**Key points:**
- No authentication required for player stats, projections, draft, and league data
- No published rate limits; community-observed limit ~1 req/s sustained
- Personal/research use: **permitted**
- Commercial use: not explicitly addressed; low risk for internal research tools
- Attribution: not required but good practice to credit "Data provided by Sleeper"

**Recommended access:** Direct API calls via `api/sleeper_api.py`

---

### FantasyPros

**ToS summary (fantasypros.com/terms):** FantasyPros explicitly prohibits:
> "automated means to access the Service or collect any data from the Service,
> including without limitation, robots, spiders, crawlers, or data mining tools"

**Key points:**
- **Automated scraping: prohibited**
- **CSV export (manual download): permitted** — their CSV download feature is
  designed for user download; no automated access requirement
- Commercial use restriction: yes — FantasyPros data cannot be redistributed
- Attribution: required when publishing any derived analysis
  — "Source: FantasyPros.com"

**Recommended access:** Manual CSV export only. Do NOT implement automated scraping.
Current `data/fantasypros_loader.py` (CSV-based) is compliant.

**Do NOT implement:** Automated web scraping of fantasypros.com

---

### ESPN

**ToS summary (espn.com/terms):** ESPN's ToS prohibits automated data collection:
> "use any robot, spider, scraper or other automated means to access the ESPN
> Services for any purpose"

ESPN's Fantasy API (`fantasy.espn.com/apis/v3/`) is undocumented and unsupported.
ESPN has blocked and deprecated these endpoints without notice in the past.

**Key points:**
- Automated scraping: **prohibited**
- Unofficial Fantasy API: technically usable but unsupported and may break
- Historical data: limited availability; no guaranteed archive
- Risk: high (ToS violation + brittle endpoint)

**Recommendation:** **Do not implement.** Risk outweighs benefit given Sleeper coverage.

---

### Yahoo

**ToS summary:** Yahoo's ToS requires OAuth 2.0 for Fantasy Sports API access.
The Fantasy Sports API (`developer.yahoo.com/fantasysports/`) is officially
supported for registered applications.

**Key points:**
- **OAuth 2.0 required** — no bulk unauthenticated access
- Personal use application: permitted with OAuth registration
- Data redistribution: prohibited
- Attribution: "Data provided by Yahoo" required in user-facing interfaces
- Historical data (2020–present): accessible via authenticated API

**Recommended access:** If Yahoo data is needed, register an OAuth application
and use the official API. **Do not scrape.** Implementation adds significant
auth overhead; deprioritized relative to Sleeper.

---

### numberFire

**ToS summary:** numberFire.com terms of service prohibits automated data collection.
No public API exists. Web scraping would require bypassing their frontend.

**Key points:**
- No public API
- Automated scraping: **prohibited**
- Data primarily duplicates FantasyPros consensus with a DFS focus

**Recommendation:** **Do not implement.** No compliant access path exists.

---

## Compliance Decision Matrix for Initiative 2

| Task | Source | Method | Status |
|------|--------|--------|--------|
| Historical projections 2022–2024 | Sleeper | API | ✅ Proceed |
| Pre-draft consensus rankings | FantasyPros | Manual CSV | ✅ Proceed (manual) |
| Weekly actuals 2022–2024 | Sleeper | API | ✅ Proceed |
| Ensemble comparison | Sleeper + FantasyPros | Combined | ✅ Proceed |
| ESPN projections | ESPN | — | ❌ Do not implement |
| Yahoo projections | Yahoo | OAuth API only | ⚠️ Low priority |

---

## Required Implementation Gates

1. **B4 (projection ingestion pipeline — #202):** May proceed with **Sleeper API only**.
   FantasyPros data must remain manual CSV. No ESPN or numberFire automation.

2. **Attribution:** Any report, notebook, or output that includes FantasyPros data
   must include: *"Expert consensus rankings courtesy of FantasyPros.com"*

3. **Rate limiting (#91):** Must be implemented before any bulk Sleeper data pull.
   Target ≤ 1 req/s with exponential backoff on 429.

4. **Logging:** All automated API calls to Sleeper should log request counts for
   audit purposes. Store in `logs/` with daily rotation.
