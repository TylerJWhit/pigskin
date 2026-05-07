# ADR-010: CLI Standardization — Command Naming, Argument Conventions, and Interface Design

**Status:** Accepted
**Date:** 2026-05-01
**Reviewed:** 2026-05-01
**Author:** Architecture Agent (via Orchestrator)
**Reviewer:** Architecture Agent
**Deciders:** Engineering team

---

## Context

`cli/commands.py` is 1,761 lines — 2.3× the 750-line threshold defined in ADR (issue #289). `cli/main.py` is also oversize. The CLI has grown without a unifying design document, resulting in:

- **Inconsistent naming**: `handle_bid_command`, `handle_sleeper_status`, `run_enhanced_mock_draft` — three different naming patterns for command handlers.
- **Mixed positional/named arguments**: `bid <player_name> [current_bid]` uses positional args; other commands use flags inconsistently.
- **No exit code contract**: Commands return ad-hoc values or print errors without standardized codes.
- **No `--json` output flag**: Machine-readable output is impossible today.
- **Unclear command taxonomy**: `bid`, `mock`, `tournament`, `sleeper`, `ping`, `undervalued` are all top-level with no grouping.

Before v1.0.0 ships, the CLI interface must be stable. All changes post-v1.0.0 are breaking changes.

**References:**
- Ollama CLI: minimal, consistent verb-noun commands (`ollama run`, `ollama list`, `ollama pull`)
- GitHub CLI (`gh`): consistent flag conventions, `--json` flag, `gh pr list`, `gh issue view`
- Issue #19: Typer migration — this ADR resolves the framework decision first

---

## Decisions

### 1. Framework: Stay on Click (Typer Migration Deferred)

**Decision:** Retain Click as the CLI framework. Typer migration (#19) is deferred to post-v1.0.0.

**Rationale:**
- The current CLI is implemented in plain Python with `sys.argv` parsing — not Click. Migrating to Click first, then Typer, is two migrations. One framework change before 1.0.0 is enough risk.
- Click provides type annotations, automatic `--help` generation, and subcommand groups — everything needed to meet this ADR's requirements.
- Typer is a thin wrapper over Click. Migrating from Click to Typer post-v1.0.0 is straightforward and low-risk.
- Typer migration (#19) remains in the backlog for v1.1.0.

**Migration plan (this ADR's scope):** Rewrite `cli/main.py` using Click's `@click.group()` / `@click.command()` decorators. `cli/commands.py` retains business logic but is split into domain-specific modules to get under 750 lines each.

---

### 2. Command Taxonomy

**Decision:** Group commands under four top-level noun groups: `draft`, `tournament`, `data`, and `sleeper`. One-off utilities (`ping`) remain as top-level commands.

```
pigskin
├── draft
│   ├── bid <player>         # Calculate bid recommendation
│   ├── mock                 # Run mock draft simulation
│   └── undervalued          # List undervalued players
├── tournament
│   └── run                  # Run elimination tournament
├── data
│   └── reload               # Reload FantasyPros player data cache
├── sleeper
│   ├── status               # Show draft status for a username
│   ├── draft <draft-id>     # Show a specific draft
│   ├── league <league-id>   # Show league rosters
│   ├── leagues              # List leagues for a username
│   └── cache                # Manage Sleeper cache
└── ping                     # Test Sleeper API connectivity
```

**Naming convention:** noun group + verb (`draft bid`, `tournament run`) following the `gh` and Ollama patterns. All command names use **kebab-case** (hyphens, not underscores).

**Rationale:** Grouping prevents namespace collision as the CLI grows (e.g., `pigskin data reload` vs an ambiguous top-level `reload`). The `gh` CLI uses this pattern successfully.

---

### 3. Argument Conventions

**Decision:**

| Type | Convention | Example |
|------|-----------|---------|
| Required inputs | Named options with `--` prefix | `--player "Josh Allen"` |
| Entity identifiers | Named options | `--draft-id 1257154391174029312` |
| Numeric tuning params | Named options with defaults | `--teams 10`, `--rounds 10` |
| Boolean flags | Flag options (no value) | `--verbose`, `--json` |
| Positional args | **Not used** | — |

**Rationale:** Named options are self-documenting in shell history and scripts. Positional args are convenient for one-off interactive use but break scripts when new arguments are added. The `gh` CLI uses this convention exclusively. The current `bid <player_name> [current_bid]` syntax will change to `pigskin draft bid --player "Josh Allen" --current-bid 25`.

**Migration note:** This is a breaking change to the command interface. It must ship before v1.0.0 so the positional-arg syntax is never part of the stable contract.

---

### 4. Help Text Standards

**Decision:** Every command must have:
1. A one-line description (shown in group `--help` output).
2. Extended help text for non-trivial commands (shown in command `--help`).
3. Every option must have a `help=` string.

**Example (target state):**
```bash
$ pigskin draft bid --help
Usage: pigskin draft bid [OPTIONS]

  Calculate a bid recommendation for a player in an auction draft.

Options:
  --player TEXT        Player name to evaluate  [required]
  --current-bid FLOAT  Current bid price (default: 1.0)
  --draft-id TEXT      Sleeper draft ID (overrides config default)
  --json               Output machine-readable JSON
  --help               Show this message and exit.
```

**Enforcement:** PR review checks that all new commands include complete `--help` text. The `qa.agent.md` AI smell checklist flags commands missing help strings.

---

### 5. Exit Code Contract

**Decision:**

| Code | Meaning |
|------|---------|
| `0` | Success — command completed as expected |
| `1` | User error — invalid arguments, player not found, bad config |
| `2` | System error — API failure, I/O error, unexpected exception |
| `3` | Not found — requested entity does not exist (player, draft, league) |

**Rationale:** Standardized exit codes enable shell scripting and CI integration. Code `3` is separated from `1` so scripts can distinguish "user typed the wrong thing" from "valid query, entity missing."

**Implementation:** All command handlers use `sys.exit(N)` or Click's `ctx.exit(N)`. The `CommandProcessor` returns a result dict with a `success` bool and optional `exit_code` int; the Click layer translates this.

---

### 6. JSON Output Flag

**Decision:** All commands that produce structured output support a `--json` flag that prints raw JSON to stdout and suppresses all other output.

**Rationale:** Machine-readable output is essential for scripting and API-less integrations. The `gh` CLI implements this pattern on every relevant command.

**JSON output contract:**
- On success: `{"status": "ok", "data": {...}}`
- On error: `{"status": "error", "code": N, "message": "..."}`
- The `data` key structure is command-specific and documented in `docs/api/cli-schema.md` (to be created).

**Scope:** `draft bid`, `draft mock`, `draft undervalued`, `tournament run`, `sleeper status`, `sleeper draft`, `sleeper league`, `sleeper leagues`. Utility commands (`ping`, `sleeper cache`) output human-readable text only.

---

## Options Considered (Framework)

| Option | Description | Decision |
|--------|-------------|----------|
| Keep `sys.argv` parsing | No framework; current state | ❌ Rejected — no auto-help, no type coercion, too much boilerplate |
| **Click** | Mature, decorator-based; `@click.group()` | ✅ Adopted for v1.0.0 |
| Typer | Click wrapper with type hints | ⏱ Deferred to v1.1.0 (#19) |
| argparse | stdlib; no subcommands without boilerplate | ❌ Rejected — inferior DX to Click |

---

## Current State vs Target State

| Aspect | Current | Target (v1.0.0) |
|--------|---------|----------------|
| Framework | `sys.argv` | Click |
| Command taxonomy | Flat, ad-hoc | 4 noun groups + utilities |
| Argument style | Mixed positional/named | Named options only |
| Help text | Docstring in `main.py` | Click `--help` on every command |
| Exit codes | Inconsistent | Defined 4-code contract |
| JSON output | Not supported | `--json` flag on all data commands |
| File size | `commands.py`: 1,761 lines | Split into domain modules < 750 lines each |

---

## Consequences

### Positive
- Stable, self-documenting CLI interface before v1.0.0.
- Named-option convention eliminates argument-order bugs in scripts.
- JSON output enables CI integration and scripting without parsing human text.
- Click auto-generates `--help` for all commands — zero maintenance burden.
- Typer migration post-v1.0.0 is a drop-in refactor (same decorator model).

### Negative
- `bid <player_name> [current_bid]` positional syntax is a breaking change. Any existing scripts using positional args must be updated.
- `cli/commands.py` split requires a non-trivial refactor PR. This is a prerequisite for staying under the 750-line threshold.
- Click introduces an explicit dependency (currently only `sys` is used).

---

## Implementation Issues

The following issues should be filed to implement decisions made in this ADR:

1. **Migrate CLI to Click** — Rewrite `cli/main.py` with `@click.group()` subcommands matching the new taxonomy. Remove `sys.argv` parsing.
2. **Split cli/commands.py** — Decompose into `cli/commands/draft.py`, `cli/commands/tournament.py`, `cli/commands/sleeper.py`, `cli/commands/data.py` — each < 750 lines.
3. **Implement `--json` flag** — Add to all data-producing commands.
4. **Standardize exit codes** — Audit all `CommandProcessor` methods for correct exit code mapping.
5. **Write CLI help text audit** — QA pass to confirm all commands have complete `--help` strings.
6. **Post-v1.0.0: Typer migration** (#19 — rebase on top of Click implementation).
