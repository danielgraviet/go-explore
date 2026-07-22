# T001: Measurement Gap Cleanup

## Goal

Make the viability benchmark tables complete enough to compare snapshot continuation against clean retries without relying on manual caveats.

## Context

The Phase 5 context-ablation smoke showed useful solve-rate and token data, but some fields are still incomplete:

- `restore_overhead_seconds` is `unknown`.
- Explicit continuation rows can miss joined `snapshot_cell_key` metadata even when the source archive has it.
- `repeated_setup_score` is often `unknown`.

Larger paid runs should not start until these gaps are either fixed or explicitly labeled as unsupported.

## Scope

- Record exact restore latency for Daytona snapshot continuations.
- Join explicit continuation snapshots back to archive/event cell metadata.
- Either compute repeated setup scores for observed runs or mark the metric unsupported with a clear warning.
- Add tests covering the new fields in continuation reports and analysis tables.

## Out of Scope

- Do not run the larger viability benchmark.
- Do not change selector policy beyond metadata needed for measurement.
- Do not make paper claims from smoke-only data.

## Suggested Starting Points

- `go_explore/continuations.py`
- `go_explore/analysis_tables.py`
- `go_explore/events.py`
- `tests/test_continuations.py`
- `tests/test_analysis_tables.py`
- `docs/experiments/context-ablation-smoke-20260722.md`

## Acceptance Criteria

- Continuation reports include restore latency when available.
- Analysis rows populate `restore_overhead_seconds` for restored snapshot jobs when available.
- Explicit snapshot continuations can recover `snapshot_cell_key` from archive/event lineage.
- Unknown repeated-work fields produce a precise warning rather than a vague missing value.

## Validation

Run focused tests:

```bash
.venv/bin/python -m pytest tests/test_continuations.py tests/test_analysis_tables.py -q
```

Regenerate one existing smoke analysis table from checked artifacts and confirm warnings are narrower than before.

## Notes / Open Questions

If Daytona does not expose restore latency directly, measure wall-clock around the restore operation in the continuation runner and label it as observed client-side restore latency.
