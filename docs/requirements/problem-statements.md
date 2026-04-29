# Problem Statements — Pigskin Fantasy Football Draft Assistant

**Status:** Draft
**Author:** Product Manager Agent
**Date:** 2026-04-28
**Version:** 1.0

---

## Critical Thinking Preamble

Before writing problem statements, I must surface two key assumptions embedded in the way this work was framed:

### Assumption 1: "The app and the lab solve different problems for different people."

**Assessment: TRUE — and it's more extreme than it first appears.**

The app and the lab are not two features of one product. They are two *products* sharing a codebase. The problems they solve are categorically different:
- The app solves a **coordination and information problem** during a time-pressured live event
- The lab solves a **research feedback loop problem** over an asynchronous, weeks-long development cycle

Conflating them in roadmap discussions leads to building features that serve neither user well.

### Assumption 2: "The lab will eventually expose results to end users."

**Assessment: UNCERTAIN — this needs an explicit decision.**

There is a plausible future where strategy win-rates are surfaced to app users: "This draft is using the Elite Hybrid strategy, which wins 42% of 12-team auctions." That would be a useful trust signal. However, it requires:
- A stable benchmark database
- A trust model (does a user actually care what algorithm is running?)
- A versioned API for lab results

For Sprint 4 and Sprint 5, **the lab is purely internal infrastructure** — no end-user exposure. If the decision changes, it must be an explicit ADR, not a silent feature addition.

**Stated assumption here:** Lab results remain internal through Sprint 5. Revisit in Sprint 6 planning.

---

## Problem Statement 1: The Production App

### Problem Title
*Real-time auction drafts are operationally chaotic, prone to errors, and leave participants without the information they need to make good decisions.*

### Who Has This Problem?
- **Primary:** Alex (League Commissioner) — running the auction
- **Secondary:** Casey (Team Owner) — bidding in real time
- **Pre-draft:** Morgan (Power User) — preparing strategy before draft day

### How Often?
- Once per season per league (annually recurring, high-stakes)
- Leagues typically run 8–14 participants; a single commissioner may run 1–3 leagues per season

### What Does "The Problem" Look Like in Practice?

Today, a commissioner running a 12-team auction draft faces:

1. **Manual tracking in a spreadsheet** → One typo in budget math silently corrupts all downstream decisions. When Alex marks the wrong team as the winner of a $45 bid, every future budget calculation is wrong. Nobody knows until the auction is over.

2. **No broadcast of live state** → Other team owners can't see the current bid, who bid it, or what budgets remain. The commissioner announces each piece of information manually — a slow and error-prone broadcast loop.

3. **No bid recommendation at nomination time** → Alex (and Casey) have to rely on memorized ADP, pre-printed auction guides, or external apps. There is no system that looks at the current state of the draft (who's been nominated, what budgets remain, which positions are unfilled) and says: *"Based on current conditions, Josh Allen is worth $38."*

4. **Post-auction pain** → Exported rosters are reconstructed from memory or late-added spreadsheet cells. Disputes arise because there is no immutable record of what happened.

### What Is the Cost of Not Solving It?
- Auctions end in disputes → commissioner loses credibility → leagues switch to snake drafts
- Bad bid decisions (overbidding early, running out of budget) reduce competitive quality → less engaging season
- Commissioner won't use the tool in future if the overhead isn't worth it

### Problem Statement (One Sentence)
> *Fantasy football commissioners and participants lack a reliable, real-time system to track auction state, enforce budget rules, and make data-driven bid decisions during a live, time-pressured draft — resulting in manual tracking errors, information asymmetry, and draft-day disputes.*

### Success Metrics

| Metric | Target | Why |
|--------|--------|-----|
| Auction completion rate | ≥ 99% | No tool failure during an active draft |
| Post-auction roster export accuracy | 100% | Zero disputes |
| Commissioner setup time (cold start) | < 5 minutes | Low barrier to adoption |
| Bid recommendation latency | < 500ms | Non-disruptive to draft pace |
| Spectator state sync latency | < 1 second | Real-time feel via WebSocket |

### How the App Solves It
The production app (`pigskin-app`) provides:
- **A live auction tracker**: every nomination, bid, and win recorded via the REST API
- **Budget enforcement**: server-side validation ensures no bid exceeds remaining budget
- **Real-time state broadcast**: WebSocket stream keeps all participants synchronized
- **Bid recommendations**: `/api/v1/recommend/bid` returns a data-driven suggested max bid, accounting for current draft state
- **Pre-draft player valuation**: `/api/v1/players/` lets Morgan build her target list before draft day

---

## Problem Statement 2: The Research Lab

### Problem Title
*Strategy quality cannot improve without a rigorous, automated feedback loop — and none exists today.*

### Who Has This Problem?
- **Primary:** Sam (Strategy Researcher) — building new strategies
- **Secondary:** Dev (Platform Developer) — maintaining quality gates

### How Often?
- Ongoing — every time a strategy is written or modified (development cycle, not event-based)
- Currently: any strategy change is assessed only by running a manual tournament and eyeballing the results

### What Does "The Problem" Look Like in Practice?

Today, creating a new bidding strategy in Pigskin involves:

1. **Writing a strategy class** in `strategies/` — straightforward
2. **Running a manual tournament** with `./pigskin tournament` — gives a winner, but n=10 to n=50 runs; not statistically meaningful
3. **No baseline champion** to compare against — "did this strategy improve things?" has no quantitative answer
4. **No gate** — any strategy, regardless of quality, can be committed to the repo and used in a real draft
5. **No audit trail** — there is no record of why a given strategy was adopted or what evidence supported it

The result: The 16 strategies in the codebase today were added organically, with no evidence that any of them are better than any other in a statistically rigorous sense. There is no "best" strategy — just the most recently added one.

**This is the research feedback loop problem:**

```
Write strategy → run 10 simulations → "seems good" → commit → never validated again
```

The lab's job is to replace this with:

```
Write strategy → run 500 simulations → statistical gate → auto-PR if PASS → human review → promote
```

### What Is the Cost of Not Solving It?
- Strategy quality degrades over time as experiments accumulate without discipline
- Developers lose confidence in which strategy is "best"
- AlphaZero development (issue #55) will be completely unmeasurable without this pipeline
- When the app's `/api/v1/recommend/bid` endpoint is built, it will use *some* strategy — and without a gate, that strategy is arbitrary

### Problem Statement (One Sentence)
> *There is no automated, statistically rigorous pipeline to evaluate whether a new bidding strategy is actually better than the current production strategy — so strategy quality improvement is unmeasurable, undisciplined, and invisible to the rest of the system.*

### Success Metrics

| Metric | Target | Why |
|--------|--------|-----|
| Gate evaluation turnaround | < 10 minutes (500 sims) | Fast enough to run per commit |
| Gate false positive rate | < 1% (p < 0.01 threshold per ADR-003) | Don't promote noise |
| Promotion lead time | ≤ 1 sprint from gate PASS to production | Strategy improvement is visible |
| Benchmark coverage | All strategies scored on same opponent set | Apples-to-apples comparison |
| Lab isolation | Zero `app/` imports from `lab/` code | No contamination |

### How the Lab Solves It
The research lab (`pigskin-lab`) provides:
- **Structured experiment management**: each experiment in `lab/experiments/<id>/` with config + results
- **Automated simulation batch runner**: 500+ runs with diverse seeds and opponents
- **Statistical gate** (`lab/promotion/gate.py`): p-value evaluation per ADR-003 specification
- **Benchmark results DB** (`lab/results_db/`): historical record of every evaluation
- **Auto-generated promotion PR**: when a gate PASS occurs, the PR is auto-created for human review
- **Isolation guarantee**: `lab/` never imports from `app/`; contamination is a CI failure

---

## How the App and Lab Differ — Complete Comparison

| Dimension | App Problem | Lab Problem |
|-----------|-------------|-------------|
| **User** | Commissioner, team owners, power users | Strategy researchers, developers |
| **Time horizon** | 2–4 hours (a single draft) | Weeks to months (a research cycle) |
| **Session type** | Real-time, interactive, time-pressured | Async, batch, time-tolerant |
| **Failure severity** | High — draft corrupted = catastrophic | Low — gate wrong = wasted compute |
| **Information needed** | Current state (who bid, how much, what's left) | Historical aggregate (what wins over time) |
| **Primary metric** | Auction completion rate | Strategy win-rate improvement |
| **Interface** | Web UI + WebSocket + REST API | CLI + SQLite + scripts |
| **Auth** | API key (Phase 1), JWT (Phase 2) | Developer access only |
| **Latency tolerance** | Sub-second | Minutes (batch acceptable) |
| **Dependency direction** | App imports from core | Lab imports from core; never from app |

### Are These the Same Product?
**No.** The app and the lab are two products sharing the `core/` package. They should be developed on separate timelines with separate success metrics and separate roadmaps. Treating them as one product risks:
- Prioritizing lab infrastructure over app reliability (wrong for Sprint 4)
- Delaying lab pipeline work because it "doesn't help the commissioner" (wrong long-term)
- Building a lab-to-user "strategy leaderboard" feature before the lab itself is working

**The correct framing:** The app is the primary user-facing product. The lab is the infrastructure that makes the app continuously better. The lab serves the app, not the user directly — at least through Sprint 5.

---

## Open Question: Does the Lab Ever Face End Users?

**Explicitly deferred.** A "strategy performance" transparency feature (showing end users what win-rate the current production strategy achieves) is conceivable and potentially valuable as a trust signal. However:

1. It requires a stable, queryable benchmark database (Sprint 5 at earliest)
2. It requires a product decision about whether users care about this information
3. It requires a UI design that makes win-rate statistics meaningful to a non-technical user

**Recommended action:** Place this in the Sprint 6 discovery backlog. Do not build toward it in Sprint 4 or Sprint 5.
