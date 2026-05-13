# GitHub Wiki Plan

**Status:** Draft — Sprint 11, Track G  
**Issues:** #297  
**Last updated:** 2026-05-13

This document defines the structure, ownership, writing standard, and rollout priority for the Pigskin Fantasy Football GitHub Wiki.

---

## 1. Page Structure

The wiki uses a flat namespace (GitHub wikis do not support subdirectories), so pages are prefixed with a category slug.

```
Home
│
├── Getting Started
│   ├── GettingStarted-Installation
│   ├── GettingStarted-QuickStart
│   └── GettingStarted-Configuration
│
├── Strategies
│   ├── Strategies-Catalog          ← mirrors docs/strategies/catalog.md
│   ├── Strategies-HowToCreate      ← mirrors docs/strategies/how-to-create.md
│   └── Strategies-LabExperiments
│
├── API
│   ├── API-Overview
│   └── API-Endpoints               ← generated from docs/api/openapi.yaml
│
├── Architecture
│   ├── Architecture-Overview
│   ├── Architecture-ADRs           ← index of docs/adr/
│   └── Architecture-LabPipeline
│
├── Development
│   ├── Development-ContributingGuide
│   ├── Development-BranchingStrategy
│   ├── Development-TestingGuide
│   └── Development-CIWorkflows
│
└── Operations
    ├── Operations-Runbook
    └── Operations-PromotionPipeline
```

---

## 2. Ownership Matrix

Each page has a **primary owner** (the agent/team responsible for keeping it current) and a **reviewer** (signs off on major changes).

| Page | Primary Owner | Reviewer | Update Cadence |
|------|---------------|----------|----------------|
| Home | Docs Agent | Lead Dev | Each sprint |
| GettingStarted-Installation | Docs Agent | DevOps | On dependency change |
| GettingStarted-QuickStart | Docs Agent | Lead Dev | Quarterly |
| GettingStarted-Configuration | Docs Agent | Backend Agent | On config schema change |
| Strategies-Catalog | Docs Agent | Strategy Agent | When strategy added/removed |
| Strategies-HowToCreate | Docs Agent | Strategy Agent | On `BaseStrategy` API change |
| Strategies-LabExperiments | Lab Agent | Strategy Agent | Each sprint |
| API-Overview | Docs Agent | Backend Agent | Each sprint |
| API-Endpoints | Backend Agent (auto-gen) | Docs Agent | Each PR to `api/` |
| Architecture-Overview | Docs Agent | Lead Dev | Quarterly |
| Architecture-ADRs | Docs Agent | Lead Dev | When ADR is merged |
| Architecture-LabPipeline | Lab Agent | Lead Dev | On pipeline change |
| Development-ContributingGuide | Docs Agent | Lead Dev | On workflow change |
| Development-BranchingStrategy | Docs Agent | Lead Dev | On branching policy change |
| Development-TestingGuide | Docs Agent | QA Agent | On test infra change |
| Development-CIWorkflows | DevOps Agent | Lead Dev | On workflow change |
| Operations-Runbook | DevOps Agent | Lead Dev | On infra change |
| Operations-PromotionPipeline | Lab Agent | Lead Dev | Sprint 12+ |

> **Agent key:**  
> - **Docs Agent** — GitHub Copilot chat, Track G work  
> - **Backend Agent** — Copilot, API / FastAPI work  
> - **Strategy Agent** — Copilot, strategies module work  
> - **Lab Agent** — Copilot, `lab/` work  
> - **DevOps Agent** — Copilot, CI/CD / Make target work  
> - **Lead Dev** — human maintainer (final approval)

---

## 3. Writing Standard

### 3.1 Tone and Voice

- **Direct and technical.** Write for Python developers; avoid over-explaining basic concepts.
- **Present tense.** "The strategy bids…" not "The strategy will bid…"
- **Second person for instructions.** "Run `pytest`…" not "The user should run…"
- **No marketing language.** Avoid "powerful", "seamless", "best-in-class".

### 3.2 Format

| Element | Guidance |
|---------|----------|
| Headings | `##` for sections, `###` for subsections; no `#` (GitHub renders page title) |
| Code blocks | Always fenced with language tag (` ```python `, ` ```bash `, ` ```yaml `) |
| Tables | Use for comparisons, parameter references, and matrices |
| Links | Use wiki-relative links: `[[Strategies-Catalog]]`; repo links use full path |
| File references | Backtick the path: `` `strategies/__init__.py` `` |
| Commands | Single-line commands inline (`` `pytest` ``); multi-step in fenced bash block |

### 3.3 Required Sections per Page

Every wiki page must include:

1. **One-line summary** at the top (plain text, no heading)
2. **Last updated** line: `_Last updated: YYYY-MM-DD (Sprint N)_`
3. **Body content** (varies by page type)
4. **Related pages** section at the bottom (2–4 wiki links)

### 3.4 Update Cadence

- **Sprint-end review:** Primary owner checks whether the page is still accurate before closing the sprint.
- **Triggered updates:** Any PR that changes a documented behavior must update the relevant wiki page in the same PR (or file a follow-up issue tagged `docs`).
- **Quarterly audit:** Lead Dev + Docs Agent review all pages for staleness each quarter.

---

## 4. Priority Pages (Sprint 12+)

Pages to create first, in order of user impact:

| Priority | Page | Rationale |
|----------|------|-----------|
| P0 | Home | Entry point; every visitor lands here |
| P0 | GettingStarted-Installation | Needed to onboard new contributors |
| P0 | Strategies-Catalog | Core reference; mirrors `catalog.md` (already written) |
| P1 | GettingStarted-QuickStart | Reduces time-to-first-draft for new users |
| P1 | Development-ContributingGuide | Needed before external contributions |
| P1 | Strategies-HowToCreate | Mirrors `how-to-create.md` (already written) |
| P2 | API-Endpoints | Auto-generated from `openapi.yaml` via `make openapi` |
| P2 | Architecture-ADRs | Index pointing to `docs/adr/` for decision history |
| P3 | Development-TestingGuide | Property test infra is non-obvious; guide reduces friction |
| P3 | Architecture-LabPipeline | Important once lab promotion (Sprint 12) is live |

---

## 5. Tooling Notes

- **Source of truth:** The `docs/` directory in the repo is canonical for ADRs, the strategy catalog, and the API spec. Wiki pages that mirror repo docs should note this and link to the source file.
- **Auto-generation:** `API-Endpoints` can be generated from `docs/api/openapi.yaml` using a script in `Makefile` (target TBD in Sprint 12).
- **Sync script:** Consider a `make wiki-sync` target (Sprint 13+) that pushes `docs/strategies/catalog.md` and `docs/strategies/how-to-create.md` to the wiki automatically on merge to `main`.
