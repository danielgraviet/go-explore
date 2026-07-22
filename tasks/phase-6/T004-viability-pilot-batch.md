# T004: Viability Pilot Batch

## Goal

Run a small paid pilot to verify that the Phase 6 manifest shape, analysis tables, and cost profile are usable before launching the full viability batch.

## Context

The pilot should answer whether the new `none`-centered design produces clean artifacts and whether `critical_parent_summary` is worth keeping in the full run.

## Scope

- Run 2-3 tasks from `docs/experiments/viability-task-set.md`.
- Include clean retry, `promising_branch + none`, and `promising_branch + critical_parent_summary`.
- Include a small `random_branch + none` selector-control slice if budget allows.
- Execute in tmux and record attach commands.
- Build analysis tables and write `docs/experiments/viability-pilot.md`.

## Out of Scope

- Do not run the full task set.
- Do not tune prompts after seeing the first task.
- Do not add `parent_summary` unless the pilot is explicitly a diagnostic ablation.

## Suggested Starting Points

- `docs/runbook.md`
- `docs/experiments/viability-task-set.md`
- `docs/experiments/main-benchmark/analysis/smoke/context-ablation-regex-log-20260722/`

## Acceptance Criteria

- Pilot jobs complete or are clearly labeled as infrastructure failures.
- Analysis tables include solve rate, cost, tokens, snapshot overhead, and restore overhead where available.
- The memo states whether the full batch should proceed unchanged, shrink, or change arms.

## Validation

Run the analysis table builder on the pilot artifacts and verify all planned jobs are accounted for:

```bash
.venv/bin/python -m go_explore.cli build-analysis-tables --help
```

Inspect every continuation report and event log referenced by the memo.

## Notes / Open Questions

Stop after the pilot if costs are materially higher than expected or if restore/lineage fields are still missing.
