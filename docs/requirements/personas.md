# User Personas — Pigskin Fantasy Football Draft Assistant

**Status:** Draft
**Author:** Product Manager Agent
**Date:** 2026-04-28
**Version:** 1.0

---

## Critical Thinking Preamble

Before defining personas, I must surface the key assumption embedded in the issue structure:

> *The issue asks for "Persona A: Manual draft tracker" and "Persona B: Sleeper-integrated live tracker" — implying these are the two primary personas.*

**That framing is wrong.**

The manual vs. Sleeper split is a **feature dimension** (how data enters the system), not a **persona dimension** (who the user is and what they need). A league commissioner using manual input and a commissioner using Sleeper sync have the same job-to-be-done; only the data source differs.

The real persona split is **by context of use**:
- **App users**: People in an active draft who need real-time recommendations
- **Lab users**: Developers/researchers who need to improve strategy quality over time

These two groups have incompatible success metrics, incompatible session lengths, incompatible failure modes, and incompatible latency tolerances. They may literally never overlap. This is explored further in `problem-statements.md`.

**Personas defined below reflect this corrected framing.**

---

## Persona 1: The Auction Commissioner ("Alex")

**Context:** App user — real-time draft day

### Profile
- Role: Fantasy league commissioner; runs the auction draft
- Technical level: Non-technical to moderate
- Session length: 60–120 minutes (full draft duration)
- Access pattern: High-frequency, read/write, time-sensitive

### Job-to-be-Done
> *"When I'm running an auction draft with 8–14 team owners, I need to track every bid, every roster, and every remaining budget in real time — so that I can enforce rules fairly and keep the draft moving without losing anyone's attention."*

### Current Pain Points
1. **Manual tracking is error-prone.** Spreadsheet tracking lags behind live bidding; one missed bid corrupts downstream budget math.
2. **No real-time budget visibility for all participants.** Other owners can't see remaining budgets, forcing the commissioner to announce it repeatedly.
3. **Rules disputes slow the draft.** No system of record for who bid what; disputes are settled by memory.
4. **No integrated bid recommendations.** The commissioner wants to know the market value of a player before nominations begin — not during the bidding war.

### Goals
- Complete the auction with zero rule disputes and no scoring errors
- Keep 8–14 participants engaged and moving (target: under 4 hours)
- Have a live record of all bids, rosters, and remaining budgets

### Success Criteria (what "done" looks like for Alex)
- Every auction action (nomination, bid, win) is recorded without manual entry
- All participants can see current state at any time
- Export of final rosters + spending is available at auction end
- Commissioner can run an auction with this tool on first try, without reading a manual

### Auth and Access Implication
Alex is the **single authority** for the draft. The app is **commissioner-controlled**. Other participants are spectators (read-only real-time state) — they do not submit bids programmatically. This resolves the ADR-002 auth question: **Phase 1 (API key, single user) is sufficient.** JWT multi-user is a future concern tied to a different use case (see Persona 3).

---

## Persona 2: The Strategy Researcher ("Sam")

**Context:** Lab user — asynchronous, research-oriented

### Profile
- Role: Developer or advanced analyst working on strategy improvement
- Technical level: High — comfortable with Python, statistics, simulation tooling
- Session length: Hours to days (experiment cycles); not time-pressured
- Access pattern: Batch-oriented, low-frequency writes, high-frequency reads of historical results

### Job-to-be-Done
> *"When I'm building a new bidding strategy, I need to run hundreds of simulations against diverse opponents and get statistically rigorous performance data — so that I know whether my strategy is actually better before it touches a real draft."*

### Current Pain Points
1. **No feedback loop.** Writing a strategy today gives no signal until someone uses it in a real draft. That's months of lag.
2. **No benchmark baseline.** There is no agreed "current champion" strategy to beat. Every comparison is ad hoc.
3. **No statistical rigor.** Tournament wins in 10 simulations mean nothing; researchers need p-values and confidence intervals.
4. **Lab contaminates production.** Today all 16+ strategies live in the same `strategies/` folder. A researcher adding an experimental strategy risks breaking a production import.
5. **No promotion contract.** Even if a strategy is better, there is no defined process to get it into the production app.

### Goals
- Run a 500-simulation benchmark in a single command
- Know within minutes whether a challenger strategy passes the statistical gate
- Have a clear, auditable path from lab to production (ADR-003 defines this)

### Success Criteria (what "done" looks like for Sam)
- Can create and run an experiment without touching `app/` code
- Gate evaluation runs automatically and produces a JSON result with p-value
- Promotion PR is auto-generated if the gate passes
- Historical benchmark results are stored and queryable

### Auth and Access Implication
Sam is a developer with direct repo/CLI access. The lab does **not need a public API**. Sam interacts via `lab/` CLI tooling and scripts. No HTTP interface needed for the lab in Sprint 4.

---

## Persona 3: The Casual Team Owner ("Casey")

**Context:** App user — real-time draft day (participant, not commissioner)

### Profile
- Role: One of 8–14 owners in an auction draft run by Alex
- Technical level: Low — uses the system as a spectator/advisory tool
- Session length: Same as draft (60–120 minutes)
- Access pattern: Read-heavy, low-write (may submit bids via a future UI)

### Job-to-be-Done
> *"When I'm bidding in an auction, I want to see what the current market value of a player is relative to my remaining budget — so that I don't overpay for a player and blow my budget in round 3."*

### Current Pain Points
1. **No in-draft budget advisor.** Casey has to mentally calculate how much to spend based on ADP and gut feel.
2. **Can't see what opponents are spending.** Without live budget visibility, Casey doesn't know if opponents are tight or flush.
3. **No positional roster guidance.** Casey loses track of which positions still need filling as the draft progresses.

### Goals
- Know whether a player is worth the current bid given remaining budget and roster needs
- Track opponent budgets to inform bidding strategy
- Avoid catastrophic roster construction mistakes (e.g., $0 left with 3 roster spots)

### Success Criteria (what "done" looks like for Casey)
- Can see a real-time bid recommendation for any nominated player
- Can see all team rosters and remaining budgets at any time
- Never accidentally overbids due to missing information

### Auth and Access Implication
Casey is a **read-only consumer** of auction state in Phase 1. Future phases may allow Casey to submit bids programmatically (triggering the JWT multi-user requirement). This is explicitly **out of scope for Sprint 4** — the commissioner controls the draft, and Casey observes.

---

## Persona 4: The Data-Savvy Power User ("Morgan")

**Context:** App user — pre-draft preparation

### Profile
- Role: Experienced fantasy player who wants to prepare before draft day
- Technical level: Moderate — comfortable with spreadsheets; not a developer
- Session length: Hours of prep work in the days before the draft
- Access pattern: Read-heavy; queries player values, exports rankings

### Job-to-be-Done
> *"Before my auction draft, I want to build a player valuation model and target list using real data — so that I enter the draft knowing exactly which players are undervalued and how much I'm willing to pay for each."*

### Current Pain Points
1. **No pre-draft valuation tool.** Bid recommendations today are run during the draft; there is no "pre-load your targets" workflow.
2. **FantasyPros data is not surfaced accessibly.** The data loader exists but there is no UI or API to query it interactively.
3. **Can't export custom rankings.** Morgan wants a CSV of players ranked by value-over-replacement, not raw ADP.

### Goals
- Generate a pre-draft auction values sheet for all players
- Query by position and filter by target budget
- Export rankings to share with league-mates

### Success Criteria (what "done" looks like for Morgan)
- Can call `GET /api/v1/players/?ranked_by=vor` and get a VOR-ranked list
- Can get a bid recommendation for any player in isolation (no live draft context needed)
- Can export player list to CSV

### Auth and Access Implication
Morgan is a **pre-draft, non-real-time user**. REST API access with an API key is sufficient. This use case validates the `/api/v1/players/` and `/api/v1/recommend/bid` endpoints as valuable even outside of a live draft session.

---

## Persona 5: The Platform Developer ("Dev")

**Context:** Lab user — building and maintaining the system itself

### Profile
- Role: Engineer maintaining the Pigskin codebase; may also be Sam's role in practice
- Technical level: High
- Session length: Daily development cycles
- Access pattern: Full read/write; runs tests, fixes bugs, deploys

### Job-to-be-Done
> *"When I'm adding a new feature or fixing a bug, I need fast feedback from the test suite and confidence that my changes don't break the core auction mechanics — so that I can ship reliably without manual regression testing."*

### Current Pain Points
1. **Test suite is not at 100% (historically).** Any failing test creates ambiguity — is my change the cause?
2. **Import paths and module structure are inconsistent.** The flat structure makes it hard to reason about dependencies.
3. **No staging environment.** Changes go from local to production with no intermediate validation.

### Goals
- `pytest` always returns clean (420/420) before any PR is merged
- Module boundaries are clear and enforced (ADR-001 migration goal)
- Local dev setup completes in under 15 minutes

### Success Criteria (what "done" looks like for Dev)
- `make test` runs the full suite in under 60 seconds
- All import errors are caught at CI time, not runtime
- New developers can clone and run in < 15 minutes

### Auth and Access Implication
No auth concerns for the developer persona — direct local access. This persona is primarily an internal quality gate signal.

---

## Summary Table

| Persona | Context | Primary Need | Auth Model | Sprint 4 Priority |
|---------|---------|-------------|------------|------------------|
| Alex (Commissioner) | App — live draft | Run a fair, complete auction | API key (Phase 1) | **PRIMARY** |
| Sam (Strategy Researcher) | Lab — async | Benchmark and promote strategies | CLI/direct | Sprint 5+ |
| Casey (Team Owner) | App — live draft | Real-time bid advisory (spectator) | Read-only API key | Phase 2 |
| Morgan (Power User) | App — pre-draft | Player valuation, export | API key (Phase 1) | Sprint 4 (endpoint shapes) |
| Dev (Platform Developer) | Internal | Reliable CI, clean structure | N/A | Always active |

---

## One Product or Two?

**Answer: Two products sharing one codebase (core/).**

The app and the lab are **not the same product**. They share domain objects (`classes/`, `config/`) but serve completely different users, timelines, and success metrics:

| Dimension | App (pigskin-app) | Lab (pigskin-lab) |
|-----------|------------------|--------------------|
| Users | Alex, Casey, Morgan | Sam, Dev |
| Session | Real-time (hours) | Async (days/weeks) |
| Latency | Sub-second required | Batch OK (minutes) |
| Failure mode | Draft corrupted = catastrophic | Gate wrong = wasted CI time |
| Success metric | Auction completion rate | Strategy win-rate improvement |
| Interface | REST API + WebSocket + Web UI | CLI + SQLite + scripts |
| Auth | API key → JWT | None (developer access) |
| Sprint 4 readiness | API schema work begins | Not started yet; Sprint 5 gate |

ADR-001 correctly captures this split. The persona analysis confirms it.
