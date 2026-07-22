# T003: Viability Manifest Planner

## Goal

Create a one-command planning path for viability experiments that does not center `parent_summary`.

## Context

Phase 5 showed that `parent_summary` is expensive and did not rescue `regex-log`. New viability manifests should make `none` the default continuation context and use `critical_parent_summary` as the main context-bearing alternate.

## Scope

- Add or extend CLI support for a viability experiment preset.
- The main arms should be:
  - clean retry,
  - branch root,
  - `promising_branch` continuations with `context_mode=none`,
  - `promising_branch` continuations with `context_mode=critical_parent_summary`,
  - optional `random_branch` control with `context_mode=none`.
- Keep `parent_summary` available only through an explicit diagnostic flag or separate manifest.
- Write manifests under `docs/experiments/viability/`.

## Out of Scope

- Do not run paid jobs in this ticket.
- Do not remove support for `parent_summary`.
- Do not solve selector scoring beyond choosing the available selector modes.

## Suggested Starting Points

- `go_explore/cli.py`
- `go_explore/experiment_runner.py`
- `go_explore/fixed_budget.py`
- `docs/runbook.md`
- `tests/test_cli.py`
- `tests/test_continuations.py`

## Acceptance Criteria

- A dry-run command can create a viability manifest for multiple tasks.
- The default continuation context in generated branch jobs is `none`.
- `critical_parent_summary` can be generated as a separate arm.
- `parent_summary` is absent from the main preset unless explicitly requested.
- Tests cover the default and the diagnostic override.

## Validation

Run:

```bash
.venv/bin/python -m pytest tests/test_cli.py tests/test_continuations.py -q
```

Also run the dry-run CLI command from the ticket and inspect the manifest contexts.

## Notes / Open Questions

If adding a new preset is too large, keep the first implementation as documented `run-experiment` invocations plus manifest naming conventions.
