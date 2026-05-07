# ADR-008: GitHub Actions Workflow Strategy and CI/CD Standardization

**Status:** Accepted
**Date:** 2026-05-01
**Reviewed:** 2026-05-01
**Author:** Architecture Agent (via Orchestrator)
**Reviewer:** Architecture Agent
**Deciders:** Engineering team

---

## Context

The `.github/workflows/` directory has grown organically from a simple CI file into ten distinct workflows. There is no documented strategy for which workflows run on which events, how branch-level quality gates differ, or how the CI, CD, and utility workflows relate to each other. Before 1.0.0 ships, this must be codified so that:

1. New contributors understand what each workflow does and when it runs.
2. CI failures are unambiguous — every gate failure has a clear owner.
3. The lab research pipeline and the production app pipeline do not interfere.
4. Dependency management is consistent across all workflows.

### Current Workflow Inventory

| File | Name | Triggers |
|------|------|---------|
| `ci.yml` | CI | push (all branches), pull_request |
| `app-ci.yml` | App CI | push (non-lab paths), pull_request |
| `lint.yml` | Lint Gate | push/PR to main, develop |
| `lab-ci.yml` | Lab CI | nightly schedule, lab PR paths, manual |
| `promotion.yml` | Strategy Promotion | manual dispatch only |
| `release.yml` | Release | manual dispatch, version tags |
| `add-to-project.yml` | Add Issues to Project Board | issues: opened |
| `sync-board-status.yml` | Sync Board Status | issues: labeled/closed/reopened, PR: opened/closed |
| `dependency-audit.yml` | Dependency Audit | weekly schedule, requirements file changes |
| `notify-ci-failure.yml` | Notify CI Failure | workflow_run on CI/App CI/Lint Gate |

### Options Considered

| Option | Description | Key Risk |
|--------|-------------|----------|
| A — Status quo | No changes; document existing layout | Duplication between ci.yml and app-ci.yml continues |
| **B — Rationalized taxonomy** | Document categories (CI / CD / Utility), define branch gates, specify uv adoption | Moderate migration effort |
| C — Full consolidation | Merge ci.yml + app-ci.yml into one file; extract shared steps as composite actions | High disruption; deferred to post-v1.0.0 |

---

## Decision

**Option B: Rationalized taxonomy with documented branch gates and uv adoption.**

Full consolidation (Option C) is deferred — it requires extracting composite actions and restructuring the trigger matrix, which is out of scope before 1.0.0. The immediate need is documentation and governance, not restructuring.

---

## Workflow Taxonomy

### Category 1: CI (Continuous Integration)

CI workflows validate code quality. They must pass before any merge.

| Workflow | Trigger | Purpose | Required Gate Level |
|----------|---------|---------|---------------------|
| `ci.yml` | push (all branches), pull_request | Baseline: install deps, run pytest | sprint/N, develop, main |
| `app-ci.yml` | push (non-lab), pull_request | App-specific: flake8 → mypy → bandit → pytest (85% coverage) → integration tests | sprint/N, develop, main |
| `lint.yml` | push/PR to main or develop | Focused flake8 logic-error gate (F8xx, E9, W6) | develop, main |

**Note:** `ci.yml` and `app-ci.yml` have overlapping coverage. Post-v1.0.0, they should be merged with path filters so one workflow handles all non-lab code.

### Category 2: Lab CI

| Workflow | Trigger | Purpose | Required Gate Level |
|----------|---------|---------|---------------------|
| `lab-ci.yml` | Nightly (1:00 AM UTC), lab PR paths, manual | Lab: migration check → simulation batch (≤ 60 min) → gate report | lab PR merges only |

Lab CI is **never required** for app or sprint branch merges. App CI and Lab CI are fully isolated.

### Category 3: CD (Continuous Delivery / Deployment)

CD workflows produce artifacts or trigger deployments. All are either manual or tag-triggered — never auto-triggered by push to main.

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `promotion.yml` | Manual dispatch only | Runs gate evaluation; if passed, opens a promotion PR — never auto-merges |
| `release.yml` | Manual dispatch or version tag push | Creates GitHub release, tags PyPI package (via submit-pypi job) |

### Category 4: Utility / Governance

Utility workflows do not block merges. They automate housekeeping.

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `add-to-project.yml` | issues: opened | Adds new issues to the GitHub Projects v2 board at Backlog |
| `sync-board-status.yml` | issues: labeled/closed/reopened; PR: opened/closed | Moves board items through lifecycle stages automatically |
| `dependency-audit.yml` | Weekly (Mon 09:00 UTC), requirements file changes | CVE scan (pip-audit) + license check; files a GitHub issue on HIGH/CRITICAL findings |
| `notify-ci-failure.yml` | workflow_run on CI/App CI/Lint Gate | Posts structured comment on PR on CI failure; applies/removes `ci:failed` label |

---

## Branch-Level Quality Gates

The 3-tier branch model (`feature/* → sprint/N → develop → main`) has three distinct merge gates:

### Merging feature/* → sprint/N
- `app-ci.yml` must pass (all jobs: flake8, mypy, bandit, pytest with 85% coverage, integration tests)
- `ci.yml` must pass
- Pre-push hook passes (flake8 + mypy + bandit + pytest locally)

### Merging sprint/N → develop
- All gates from feature → sprint
- `lint.yml` must pass
- `notify-ci-failure.yml` may not have applied `ci:failed` label to the sprint branch PR

### Merging develop → main
- All gates from sprint → develop
- `dependency-audit.yml` must show no unresolved HIGH/CRITICAL CVEs (checked manually before release)
- `release.yml` is triggered after merge (manually or via tag)

Lab branches follow their own gate: `lab/** → develop` requires `lab-ci.yml` to pass.

---

## Dependency Management: uv Adoption

All workflow `Install dependencies` steps will migrate from `pip install -r requirements.txt` to `uv sync`. This is a prerequisite for ADR-009 (contributor onboarding).

**Target state for each workflow:**
```yaml
- name: Install uv
  uses: astral-sh/setup-uv@v3
  with:
    version: "latest"

- name: Install dependencies
  run: uv sync --all-extras
```

**Caching:** `setup-uv@v3` provides automatic caching of the uv cache directory (`~/.cache/uv`). No separate `actions/cache` step is needed.

**Migration order:** `ci.yml` → `app-ci.yml` → `lint.yml` → `lab-ci.yml` → `promotion.yml` → `release.yml`. Implementation tracked in a separate issue per workflow.

---

## Caching Strategy

| Item | Current | Target |
|------|---------|--------|
| Python packages | pip (no cache) | uv (automatic cache via setup-uv) |
| Lab SQLite results | Not cached | Not cached (SQLite is in the repo fixture; fresh per run) |
| Lab simulation output | Artifact upload | Artifact upload (no change) |

---

## Workflow Reuse (Post-v1.0.0)

The following shared steps appear in multiple workflows and are candidates for composite actions:

1. **Python + uv setup**: appears in every workflow → extract to `.github/actions/setup-python-uv/`
2. **flake8 logic-error gate**: duplicated in `ci.yml`, `app-ci.yml`, `lint.yml` → extract to reusable workflow
3. **Linked-issue extraction**: used in `sync-board-status.yml` → could be a JS action if logic grows

Extraction is deferred to post-v1.0.0 to avoid churn before the release milestone.

---

## Consequences

### Positive
- Every workflow is categorized (CI / Lab CI / CD / Utility) with documented triggers and gate levels.
- Branch-level merge requirements are explicit and auditable.
- uv adoption removes `pip install` inconsistency and adds deterministic caching.
- Lab and app pipelines are clearly isolated — lab CI failures cannot block app merges.

### Negative
- `ci.yml` and `app-ci.yml` remain as two separate files until post-v1.0.0 consolidation. This is a known duplication accepted for stability.
- uv migration requires updating each workflow file individually. Each change is a separate PR to keep diffs reviewable.

---

## Implementation Issues

The following issues should be filed to implement decisions made in this ADR:

1. **Migrate all workflows to uv** — one issue per workflow (6 total)
2. **Post-v1.0.0: Merge ci.yml + app-ci.yml** — filed as backlog
3. **Post-v1.0.0: Extract composite actions** — filed as backlog
