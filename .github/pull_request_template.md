## Summary

<!-- One paragraph: what does this PR do and why? -->

Closes #<!-- issue number -->

## Type of Change

- [ ] Bug fix (`fix/`)
- [ ] New feature (`feat/`)
- [ ] Refactor (`refactor/`)
- [ ] Tests only (`test/`)
- [ ] Docs / chore (`docs/` / `chore/`)
- [ ] Performance (`perf/`)

## Changes

<!-- Bullet list of what changed -->

-

## Testing

- [ ] New or updated tests exist for this change
- [ ] `pytest tests/ -x -q` passes locally
- [ ] For bug fixes: regression test added that would have caught the bug before the fix
- [ ] For features: happy path and at least one edge case covered

```bash
# Test command run and output:

```

## Code Review Checklist

### Correctness
- [ ] Logic is correct for auction mechanics / VOR / budget constraints
- [ ] Edge cases handled (empty rosters, zero budgets, position scarcity)
- [ ] No off-by-one errors in nomination cycles or draft rounds

### Code Standards
- [ ] PEP 8 compliant, 120-char line limit
- [ ] Type hints on all new function signatures
- [ ] No magic numbers — constants in `config/` or named constants
- [ ] Absolute imports only (no relative imports)

### Architecture
- [ ] Strategies inherit from `base_strategy.py` and implement `calculate_bid()`
- [ ] Budget logic uses `BudgetConstraintManager`, not inline math
- [ ] No circular imports introduced

### Security
- [ ] No hardcoded secrets or API tokens
- [ ] External API inputs (Sleeper) validated before use
- [ ] No path traversal in file loading

### Performance
- [ ] VOR calculations cached where applicable
- [ ] MCTS iterations bounded appropriately

## Notes for Reviewers

<!-- Anything specific you want reviewers to focus on, or context they need -->
