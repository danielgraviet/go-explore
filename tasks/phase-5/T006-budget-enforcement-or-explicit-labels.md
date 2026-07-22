# T006: Budget Enforcement Or Explicit Labels

## Goal

Make benchmark budget semantics honest: either enforce per-job budgets or clearly label runs as planning-only everywhere they are reported.

## Context

The `regex-log-r3` smoke used planned token budgets, but actual token accounting exceeded those budgets. The analysis table correctly reports `budget_enforcement=planning_only`, but the benchmark CLI and docs can still make the run sound fixed-budget.

Depends on:

- P3-T003: Fixed-Budget Run Planner
- P3-T006: Analysis Tables v1

## Scope

Choose and implement one of:

- real per-job budget enforcement if Harbor/agent hooks make this practical, or
- stronger planning-only labels in CLI output, manifests, runbooks, and analysis warnings.

The implementation should prevent readers from treating planning-only runs as strict fixed-budget comparisons.

## Out of Scope

- Do not redesign the full benchmark plan.
- Do not tune token budgets for all tasks.
- Do not rerun paid experiments.

## Suggested Starting Points

- `go_explore/fixed_budget.py`
- `go_explore/experiment_runner.py`
- `go_explore/analysis_tables.py`
- `docs/experiments/main-benchmark.md`
- `docs/runbook.md`
- `tests/test_experiment_runner.py`
- `tests/test_analysis_tables.py`

## Acceptance Criteria

- CLI output and generated reports clearly state whether budgets are enforced or planning-only.
- Analysis warnings flag planning-only runs when a strict budget comparison is requested or implied.
- Tests cover the chosen behavior.
- Documentation tells users how to interpret token budget fields.

## Validation

Run:

```bash
.venv/bin/python -m pytest tests/test_experiment_runner.py tests/test_analysis_tables.py tests/test_cli.py -q
```

If implementation touches docs only, still run the relevant unit tests unless no code changed.

## Notes / Open Questions

Prefer explicit labels first if real enforcement would be a large, risky change.
