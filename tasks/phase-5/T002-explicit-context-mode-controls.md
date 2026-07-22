# T002: Explicit Context Mode Controls

## Goal

Make continuation context transfer explicit and configurable, starting with `parent_summary` and `none`.

## Context

Continuations currently inherit parent trajectory text implicitly because the snapshot backend writes `/tmp/go_explore_context.md` into the sandbox and `SnapshotAwareAgent` appends it to the prompt. This makes it hard to test whether failures come from the restored environment or inherited parent text.

Depends on:

- P2-T006: Continuation Context Modes Spec
- P5-T001: Regex-Log R3 Result Audit

## Scope

Implement explicit support for:

- `context_mode=parent_summary`: current behavior, but recorded intentionally.
- `context_mode=none`: child receives the restored sandbox state without appended parent context.

Thread the mode through continuation planning, Harbor command construction, snapshot-aware agent setup, reports, manifests, and analysis rows where applicable.

## Out of Scope

- Do not implement `critical_parent_summary`.
- Do not implement clean/diff start-state baselines.
- Do not rerun live Daytona experiments in this ticket.

## Suggested Starting Points

- `go_explore/continuations.py`
- `go_explore/experiment_runner.py`
- `go_explore/agents/snapshot_agent.py`
- `go_explore/snapshots/backends.py`
- `go_explore/analysis_tables.py`
- `tests/test_continuations.py`
- `tests/test_snapshot_agent.py`

## Acceptance Criteria

- A planned full-snapshot continuation can specify `context_mode=none`.
- With `context_mode=none`, the child agent does not append `/tmp/go_explore_context.md` to the task prompt.
- Existing default behavior remains `parent_summary`.
- Continuation reports and analysis rows record the selected context mode.
- Unit tests cover both context modes without requiring live Daytona.

## Validation

Run:

```bash
uv run pytest tests/test_continuations.py tests/test_snapshot_agent.py tests/test_analysis_tables.py -q
```

If relevant tests live elsewhere after implementation, include them in the PR notes.

## Notes / Open Questions

Prefer a small explicit flag or extra argument over hidden behavior. The next ticket will add the critical-summary prompt.
