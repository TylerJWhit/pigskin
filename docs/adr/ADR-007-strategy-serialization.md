# ADR-007: Strategy Serialization — StrategyConfig + YAML Registry

**Status:** Accepted  
**Date:** 2026-05-01  
**Author:** Architecture Agent (Sprint 7, issue #258)  
**Deciders:** TylerJWhit  
**Supersedes:** None  
**Related:** ADR-003 (Strategy Promotion Pipeline), #255 (Strategy Audit), #259 (Implementation)

---

## Context

The pigskin codebase has 18 registered strategies. The Strategy Audit (#255) found that 5 of them are **parameter variants** — they implement no unique decision logic, only different scalar values passed to an existing base class constructor. These 5 are pre-benchmark removal candidates.

If the benchmark (#261) clears additional parameter variants for removal, the remaining variants should not require separate Python files. The current system has no way to express "same algorithm, different parameters" without writing a new class.

**Problem:** Every parameter variant requires:
1. A new Python file under `strategies/`
2. Manual registration in `AVAILABLE_STRATEGIES` dict
3. A class body that does nothing except call `super().__init__(param_overrides)`

This creates proliferation (18 files), maintenance overhead, and makes the strategy registry opaque.

**Goal:** Allow parameter variants to be defined as YAML configuration files instead of Python classes, while keeping the Python API fully backward-compatible.

---

## Decision

Introduce a `StrategyConfig` Pydantic model and an extended `StrategyRegistry` that can instantiate strategies from YAML configs. Existing Python-class strategies continue to work unchanged.

---

## Architecture

### `StrategyConfig` Model

```python
# strategies/strategy_config.py
from pydantic import BaseModel, field_validator
from typing import Any

class StrategyConfig(BaseModel):
    """Validated configuration for a YAML-defined strategy variant."""
    name: str                        # registry key, e.g. 'aggressive_vor'
    display_name: str                # human-readable label
    description: str = ""
    base_class: str                  # must be in STRATEGY_CLASS_ALLOWLIST
    version: str = "1.0.0"
    parameters: dict[str, Any] = {}  # passed as **kwargs to base_class.__init__
    tags: list[str] = []

    @field_validator("base_class")
    @classmethod
    def base_class_in_allowlist(cls, v: str) -> str:
        from strategies import STRATEGY_CLASS_ALLOWLIST
        if v not in STRATEGY_CLASS_ALLOWLIST:
            raise ValueError(
                f"base_class '{v}' is not in the strategy allowlist. "
                f"Valid values: {sorted(STRATEGY_CLASS_ALLOWLIST)}"
            )
        return v
```

### Allowlist

The allowlist is a **hardcoded module-level dict** — no dynamic import, no `eval()`. Only the 8 canonical base classes identified by the Strategy Audit (#255) are permitted:

```python
# strategies/__init__.py
STRATEGY_CLASS_ALLOWLIST: dict[str, type] = {
    "ValueBasedStrategy":      ValueBasedStrategy,
    "BalancedStrategy":        BalancedStrategy,
    "ConservativeStrategy":    ConservativeStrategy,
    "AggressiveStrategy":      AggressiveStrategy,
    "EnhancedVorStrategy":     EnhancedVorStrategy,
    "AdaptiveStrategy":        AdaptiveStrategy,
    "EliteHybridStrategy":     EliteHybridStrategy,
    "BasicStrategy":           BasicStrategy,
}
```

> **Security constraint:** `base_class` is resolved exclusively from this hardcoded dict. There is no `eval()`, no `importlib.import_module()`, no `getattr(module, name)` with user-supplied names. Adding a new base class to the allowlist requires a code change + PR review.

### YAML File Format

YAML configs live in `lab/strategies/configs/*.yaml`. Example:

```yaml
# lab/strategies/configs/aggressive_vor.yaml
name: aggressive_vor
display_name: "Aggressive VOR"
description: "VOR strategy with elevated aggression for high-floor auctions"
base_class: EnhancedVorStrategy
version: "1.0.0"
parameters:
  aggression: 1.4
  vor_multiplier: 1.2
  scarcity_weight: 0.8
tags: [vor, aggressive, lab]
```

### Discovery

YAML files are **not** parsed at import time. They are loaded lazily:
- `StrategyRegistry.from_yaml(path)` — load a single file
- `StrategyRegistry.discover_yaml_configs(directory)` — load all `.yaml` files in a directory

Lab benchmarks call `discover_yaml_configs("lab/strategies/configs/")`. Production code does not call this unless explicitly configured.

### Extended `StrategyRegistry` API

```python
# strategies/__init__.py  (existing function extended)

def create_strategy(strategy_name: str, **kwargs) -> Strategy:
    """Instantiate a strategy by name. 
    
    Lookup order:
    1. AVAILABLE_STRATEGIES (existing Python-class strategies)
    2. Registered YAML configs (if any have been loaded via register_yaml_config)
    Raises ValueError if not found in either.
    """
    ...

def register_yaml_config(config: StrategyConfig) -> None:
    """Register a YAML-defined strategy variant in the runtime registry."""
    ...

def from_yaml(path: str) -> Strategy:
    """Load a StrategyConfig from a YAML file and instantiate it."""
    ...
```

### `AVAILABLE_STRATEGIES` Shim

The existing `AVAILABLE_STRATEGIES` dict remains **unchanged** for backward compatibility. It is populated at import time with all Python-class strategies. YAML-registered strategies are stored in a separate `_YAML_STRATEGY_REGISTRY` dict. `create_strategy()` checks both, in that order.

### Parameter Validation

`StrategyConfig` validates that `parameters` can be passed to the `base_class.__init__` signature using Python's `inspect.signature`. This validation occurs at load time (when `from_yaml` is called), not at instantiation time.

```python
def _validate_parameters(config: StrategyConfig) -> None:
    cls = STRATEGY_CLASS_ALLOWLIST[config.base_class]
    sig = inspect.signature(cls.__init__)
    valid_params = set(sig.parameters) - {"self"}
    invalid = set(config.parameters) - valid_params
    if invalid:
        raise ValueError(
            f"StrategyConfig '{config.name}': "
            f"parameters {invalid} not accepted by {config.base_class}.__init__"
        )
```

---

## Migration Path

### Phase 1 — Core infrastructure (Sprint 7 via #259)
1. Create `strategies/strategy_config.py` — `StrategyConfig` Pydantic model
2. Extend `strategies/__init__.py` — `register_yaml_config`, `from_yaml`, `discover_yaml_configs`
3. Add `STRATEGY_CLASS_ALLOWLIST` to `strategies/__init__.py`
4. Add unit tests for allowlist enforcement, YAML loading, parameter validation

### Phase 2 — Convert surviving parameter variants to YAML (Sprint 8 via #260)
1. After benchmark (#261) removes failing strategies, convert remaining parameter variants to `lab/strategies/configs/*.yaml`
2. Delete the corresponding Python files
3. Update lab benchmark runner to call `discover_yaml_configs()`

### Phase 3 — Production registry migration (Sprint 9+)
1. If YAML configs prove stable in lab, evaluate moving them to `strategies/configs/`
2. Update `AVAILABLE_STRATEGIES` shim to auto-include YAML configs at startup
3. Full Python-file deletion for converted variants

---

## Consequences

### Positive
- Parameter variants no longer require Python files
- Strategy registry becomes data-driven and auditable
- Lab can iterate on hyperparameters without code changes
- Security: base class allowlist prevents injection attacks via YAML inputs

### Negative
- Two registries (`AVAILABLE_STRATEGIES` + `_YAML_STRATEGY_REGISTRY`) adds lookup complexity
- YAML configs are not type-checked by IDEs until `StrategyConfig` model is loaded
- Discovery is lazy — misconfigured YAML files fail at benchmark start, not at import time

### Neutral
- No change to existing Python strategy classes or their tests
- No change to CLI or existing API callers

---

## Alternatives Considered

### Alternative A: `importlib`-based dynamic loading
**Rejected.** Allowing arbitrary class names to be resolved from user-supplied YAML input is an object injection / arbitrary code execution risk (OWASP A03:2021 Injection). The hardcoded allowlist is non-negotiable.

### Alternative B: Subclass every variant in Python, add YAML metadata only
**Rejected.** This solves the discoverability problem but does not reduce the number of Python files — the primary maintenance motivation.

### Alternative C: Plugin registration via `entry_points`
**Rejected** for Sprint 7 scope. The project is a single-repo monolith; setuptools entry points add packaging overhead with no benefit until the lab is a separate installable package.

---

## References

- #255 — Strategy audit (provides canonical base class list)
- #256 — Benchmark validity spec
- #259 — `StrategyConfig` + `StrategyRegistry` implementation
- #260 — YAML configs for surviving parameter-variant strategies
- ADR-003 — Strategy promotion pipeline
- OWASP A03:2021 — Injection (motivates allowlist constraint)
