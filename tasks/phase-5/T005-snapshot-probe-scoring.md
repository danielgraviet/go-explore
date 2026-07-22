# T005: Snapshot Probe Scoring

## Goal

Improve archive selection by giving snapshots credit for task-relevant validation signal, not only file edits or discovery steps.

## Context

In `regex-log-r3`, branch continuations selected snapshots that looked active but still contained wrong regex work. For tasks like regex repair, local tests or verifier-adjacent probes are more useful than generic "changed file" scoring.

Depends on:

- P5-T001: Regex-Log R3 Result Audit

## Scope

Add a generic probe-signal extraction path that can score snapshot candidates using evidence from recent commands/output.

At minimum, detect and expose signals such as:

- local test commands,
- successful/failed assertions,
- obvious error output,
- task-relevant validation commands from trajectory output.

Use the signal in archive scoring behind a small, testable policy change.

## Out of Scope

- Do not run the real verifier during snapshot selection.
- Do not build task-specific probes for every benchmark task.
- Do not require live Daytona for tests.

## Suggested Starting Points

- `go_explore/snapshots/policies.py`
- `go_explore/snapshots/replay.py`
- `go_explore/agents/snapshot_agent.py`
- `go_explore/repeated_work.py`
- `tests/test_snapshot_components.py`
- `tests/test_snapshot_replay.py`

## Acceptance Criteria

- Snapshot candidate metadata includes extracted validation/probe signals.
- Archive scoring can prefer a candidate with stronger validation evidence over a generic file-edit candidate.
- Negative/error evidence can reduce or avoid promoting a candidate.
- Tests cover positive, negative, and neutral probe signals.

## Validation

Run:

```bash
uv run pytest tests/test_snapshot_components.py tests/test_snapshot_replay.py tests/test_archive.py -q
```

If this changes analysis output, also run:

```bash
uv run pytest tests/test_analysis_tables.py -q
```

## Notes / Open Questions

Keep the first scoring rule transparent and debuggable. It is better to emit simple reasons than to hide scoring behind a clever heuristic.
