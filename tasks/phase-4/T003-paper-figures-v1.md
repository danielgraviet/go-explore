# T003: Paper Figures V1

## Goal

Generate the first set of figures and tables needed to fill in the essay.

## Context

The essay names specific result shapes: solve rate, cost, unique task overlap, branch lift, repeated work, overhead, and oracle gap. This ticket turns Phase 4 result tables into those artifacts.

Depends on:

- P4-T002: Main Benchmark Execution
- P3-T006: Analysis Tables V1

## Scope

Generate figures or tables for:

- solve rate by method,
- cost per solved task,
- unique task overlap,
- branch success by snapshot event type,
- promising-vs-random branch lift,
- repeated setup work,
- snapshot overhead,
- oracle gap if labels exist.

Save outputs under `docs/experiments/figures/` or the path established by the analysis scripts.

## Out of Scope

- Do not rewrite the essay in this ticket.
- Do not invent missing oracle labels.
- Do not hide missing plots.

## Suggested Starting Points

- `docs/essay.md`
- `docs/experiment-data-contract.md`
- outputs from P3-T006

## Acceptance Criteria

- Each figure has source data and a short interpretation.
- Missing figures are explicitly explained.
- Results can be regenerated from scripts plus local job artifacts.

## Validation

Run the analysis/plot script against Phase 4 result tables and inspect generated artifacts.

## Notes / Open Questions

If a figure is too sparse to be meaningful, produce the table and state why the plot is deferred.
