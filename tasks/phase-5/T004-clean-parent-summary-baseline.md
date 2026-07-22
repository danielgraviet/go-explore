# T004: Clean Parent Summary Baseline

## Goal

Add a baseline that starts from a clean environment but gives the child parent context, so we can separate memory transfer from restored machine state.

## Context

`regex-log-r3` cannot tell whether continuation failed because the snapshot state was bad, because parent context was bad, or because both interacted. `clean + parent_summary` isolates the context channel.

Depends on:

- P5-T002: Explicit Context Mode Controls

## Scope

Implement planning and execution support for:

- `start_state_type=clean`
- `context_mode=parent_summary`

The child should run in a fresh Harbor/Daytona environment while receiving a parent summary artifact through a controlled prompt or mounted/copied artifact path.

## Out of Scope

- Do not implement diff-only execution.
- Do not add LLM transcript summarization.
- Do not change archive scoring.

## Suggested Starting Points

- `go_explore/continuations.py`
- `go_explore/harbor.py`
- `go_explore/experiment_runner.py`
- `go_explore/agents/snapshot_agent.py`
- `tests/test_continuations.py`
- `tests/test_harbor.py`

## Acceptance Criteria

- The planner can produce a clean parent-summary continuation job.
- The job does not pass `snapshot_template_name`.
- Reports and analysis rows distinguish this from full-snapshot continuation.
- Tests cover command construction and metadata.

## Validation

Run:

```bash
uv run pytest tests/test_continuations.py tests/test_harbor.py tests/test_analysis_tables.py -q
```

Add any new targeted test file to the validation list in the PR.

## Notes / Open Questions

Keep the first implementation simple. If artifact injection into a clean sandbox is awkward, start with prompt-only parent summary and document the limitation.
