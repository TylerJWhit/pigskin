# ADR-009: Open Source Contributions Workflow and Onboarding Strategy

**Status:** Accepted
**Date:** 2026-05-01
**Reviewed:** 2026-05-01
**Author:** Architecture Agent (via Orchestrator)
**Reviewer:** Architecture Agent
**Deciders:** Engineering team

---

## Context

Pigskin is moving toward an open-source release. Before accepting outside contributors, the project needs a documented, community-friendly contribution workflow. Key decisions must be made about: environment management, contribution model, DCO vs CLA, PR size policy, code of conduct, and review SLAs.

This ADR draws from four reference communities:

| Community | Key Practice Adopted |
|-----------|---------------------|
| **freeCodeCamp** | Welcoming tone, `good first issue` / `help wanted` labeling, clear CONTRIBUTING.md |
| **Linux Kernel** | Strict commit message discipline (Conventional Commits, already enforced by our `.githooks/commit-msg`) |
| **React / Next.js** | PR checklist template, size limits requiring prior ADR for large changes |
| **Ollama** | `uv` for Python environment management, minimal setup steps |

---

## Decisions

### 1. Environment Management: Adopt `uv`

**Decision:** Replace `pip` + `requirements*.txt` with `uv` as the standard environment manager.

**Rationale:** `uv` provides:
- Deterministic installs via `uv.lock`
- Single command contributor onboarding: `uv sync`
- Consistent behavior between local dev and CI (per ADR-008)
- Zero-config caching

**Target state:**
```bash
# Clone + setup in 3 commands
git clone https://github.com/TylerJWhit/pigskin
cd pigskin
uv sync
```

A `pyproject.toml` (or `uv.lock`) at the repo root replaces all `requirements*.txt` files. `requirements.txt` is kept as a generated export for deployment pinning only.

**Implementation:** Filed as a separate issue (uv migration).

---

### 2. Contribution Workflow: Branch-and-PR (Fork Optional)

**Decision:** External contributors use the standard fork-and-PR model. Core team members use the 3-tier branch model (ADR-008, `.githooks/pre-push` guard).

**Rationale:**
- Fork-and-PR is the universal OSS pattern and requires no special repository access.
- Core team retains write access and continues using `feature/* → sprint/N → develop`.
- All contributions — internal and external — go through PR review before merging.

**Workflow for external contributors:**
1. Fork the repository.
2. Create a feature branch from `develop`: `git checkout -b feat/<slug>`
3. Make changes following the coding standards in `CONTRIBUTING.md`.
4. Open a PR targeting `develop`.
5. Address review feedback. CI must be green before merge.

---

### 3. Issue Labeling for Contributors

**Decision:** Adopt `good first issue` and `help wanted` as first-class labels.

| Label | Meaning |
|-------|---------|
| `good first issue` | Isolated, well-scoped issue requiring no deep context. Ideal for new contributors. |
| `help wanted` | Maintainers welcome external help. May require some codebase knowledge. |

These labels are applied at triage. Issues labeled `good first issue` must include: clear acceptance criteria, a pointer to the relevant file(s), and an estimate of scope (< 100 lines changed).

---

### 4. PR Size Policy

**Decision:** Maximum **500 lines changed** per PR. Larger changes require a prior ADR or design doc.

**Rationale:**
- Large PRs are harder to review and more likely to introduce bugs.
- 500 lines aligns with the React/Next.js community standard.
- ADR-010 files > 750 lines are flagged by the QA agent — the 500-line PR cap is complementary.

**Exceptions:**
- Auto-generated files (e.g., `uv.lock`, migration files) are excluded from the line count.
- ADR documents are excluded (they are documentation, not code).
- If a PR must exceed 500 lines, a design doc or ADR must be linked in the PR body.

---

### 5. Code of Conduct

**Decision:** Adopt the **Contributor Covenant v2.1** verbatim.

**Rationale:** Industry standard for OSS projects. Well-understood by contributors. Provides clear enforcement procedures without requiring us to author enforcement policies from scratch.

**File:** `CODE_OF_CONDUCT.md` at the repo root, linked from `CONTRIBUTING.md` and `README.md`.

---

### 6. DCO vs CLA

**Decision:** Use **DCO (Developer Certificate of Origin)**, not a CLA.

**Rationale:**
- CLA requires a signature infrastructure (CLA bot, legal review) that is disproportionate for this project's stage.
- DCO is a lightweight alternative: contributors sign off each commit with `git commit -s`, asserting they have the right to submit the code under the project's license.
- DCO is used by the Linux Kernel, CNCF projects, and many OSS tools.
- The `.githooks/commit-msg` hook can be extended to check for `Signed-off-by:` lines once the project opens to external contributors.

**DCO enforcement:** Manual for now (reviewer checks in PR review). Automated via `probot/dco` GitHub App once the project is public.

---

### 7. Review SLA

**Decision:**

| Contributor Type | First Response SLA | Full Review SLA |
|-----------------|-------------------|----------------|
| Core team member | N/A (self-review) | 2 business days |
| External contributor (`good first issue`) | 2 business days | 5 business days |
| External contributor (other) | 3 business days | 7 business days |

**Rationale:** Unresponsive maintainers are the #1 reason OSS contributors abandon a project (freeCodeCamp research). Setting explicit SLAs creates a maintainability commitment that builds contributor trust.

SLAs are documented in `CONTRIBUTING.md` and tracked informally until the project reaches a contributor volume that warrants tooling.

---

## Options Considered (Environment Management)

| Option | Description | Decision |
|--------|-------------|----------|
| Keep pip + requirements.txt | No change; familiar to most contributors | ❌ Rejected — inconsistent installs, no lock file |
| Poetry | Mature, popular; pyproject.toml-based | ❌ Rejected — heavier than uv, not needed at this scale |
| **uv** | Fast, deterministic, uv.lock, minimal setup | ✅ Adopted |
| Conda | Great for scientific Python | ❌ Rejected — overkill; not relevant to our dependencies |

---

## Consequences

### Positive
- Contributors can onboard in a single `uv sync` command.
- PR size policy reduces review burden and keeps diffs reviewable.
- DCO gives legal clarity without CLA infrastructure overhead.
- Review SLAs set a maintainability commitment that builds trust with the community.
- Contributor Covenant provides a known, well-respected CoC.

### Negative
- uv migration requires updating all `requirements*.txt` workflows and documentation.
- 500-line PR cap may require splitting some large feature implementations into multiple PRs — adding coordination overhead for core team work.
- DCO is manual until `probot/dco` is installed — one more reviewer checklist item.

---

## Implementation Issues

The following issues should be filed to implement decisions made in this ADR:

1. **Write CONTRIBUTING.md** — covers: fork model, branch naming, commit format, PR checklist, DCO, CoC reference, review SLA
2. **Add CODE_OF_CONDUCT.md** — Contributor Covenant v2.1 verbatim
3. **uv migration** — replace pip + requirements.txt across all workflows and docs (references ADR-008)
4. **Add `good first issue` and `help wanted` labels** — apply to 3–5 existing backlog issues
5. **Extend commit-msg hook for DCO** — optional; deferred until project is public
6. **Install probot/dco GitHub App** — deferred until project is public
