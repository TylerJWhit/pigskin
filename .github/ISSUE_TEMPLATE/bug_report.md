---
name: Bug Report
about: Something is broken or behaving unexpectedly
title: "fix: "
labels: bug
assignees: ""
---

## Description

<!-- Clear, concise description of the bug -->

## Steps to Reproduce

1.
2.
3.

## Expected Behavior

<!-- What should happen -->

## Actual Behavior

<!-- What actually happens — include stack trace if available -->

```
<paste error/traceback here>
```

## Environment

- Python version: <!-- python --version -->
- Branch/commit: <!-- git log --oneline -1 -->
- Command run: <!-- e.g. python -m cli.main auction simulate -->

## Subsystem

- [ ] Auction engine
- [ ] Budget constraints / BudgetConstraintManager
- [ ] Strategy (`strategies/`)
- [ ] AlphaZero / MCTS
- [ ] CLI
- [ ] Web UI / WebSocket
- [ ] Sleeper API integration
- [ ] Data loading / VOR
- [ ] Tests

## Severity

- [ ] P0 — Production down / data corruption
- [ ] P1 — Major functionality broken, no workaround
- [ ] P2 — Significant issue, workaround exists
- [ ] P3 — Minor / cosmetic
