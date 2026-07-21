# T001: Experiment Data Contract

## Goal

Define the task-level, run-level, and event-level artifacts needed to support the claims in `docs/essay.md`.

## Context

The essay claims more than solve rate. It needs evidence about budget, lineage, repeated work, snapshot overhead, branch success, and state fidelity. Before implementing more logging or analysis, contributors need a shared artifact contract.

Relevant docs:

- `docs/essay.md`
- `docs/phase-1-continuation-benchmark.md`
- `docs/archive-docs/code.md`
- `docs/archive-docs/results.md`

## Scope

Write `docs/experiment-data-contract.md` defining:

- task-level summary fields,
- run-level summary fields,
- event-level JSONL records,
- required vs optional fields,
- how each field maps to current Harbor, Daytona, archive, continuation, and trajectory artifacts,
- examples for one task row, one run row, and representative event records.

## Out of Scope

- Do not implement new logging in this ticket.
- Do not run a live benchmark.
- Do not change existing report formats.

## Suggested Starting Points

- `docs/essay.md`
- `go_explore/continuations.py`
- `go_explore/results.py`
- `go_explore/snapshots/archive.py`
- `go_explore/snapshots/metrics.py`
- `tests/test_continuations.py`

## Acceptance Criteria

- The contract includes concrete examples for task-level, run-level, and event-level artifacts.
- It identifies fields that already exist today and fields that require follow-up implementation.
- It covers budget, lineage, snapshots, commands, tests, verifier outcomes, and repeated-work analysis.
- It states how missing or unknown fields should be represented.

## Validation

Compare the contract against current code and any available local `jobs/` artifacts. If no useful jobs are available, state that validation was against code and docs only.

## Notes / Open Questions

Keep the contract practical. Prefer a small set of fields that can be implemented in Phase 2 over a perfect schema that blocks progress.
