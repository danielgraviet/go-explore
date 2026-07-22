# Context Ablation Smoke: Regex-Log

## Summary

`phase5-context-ablation-regex-log-20260722` completed as a paid Daytona smoke on July 22, 2026. It compared one clean scratch retry, one clean branch root, and three continuations restored from the same root snapshot with different context modes.

No method solved `regex-log`. The strongest signal is that removing parent context reduced token usage sharply, but did not recover success from the selected snapshot. This weakens the narrow hypothesis that inherited prompt context alone explains the branch failures. It is more consistent with the restored state itself being a wrong-solution basin, with parent summaries adding extra token cost and possibly extra anchoring.

Primary artifacts:

- `scripts/phase5_context_ablation_smoke.sh`
- `jobs/phase5-context-ablation-regex-log-20260722-tmux.log`
- `docs/experiments/main-benchmark/analysis/smoke/context-ablation-regex-log-20260722/run-summary.csv`
- `docs/experiments/main-benchmark/analysis/smoke/context-ablation-regex-log-20260722/task-summary.csv`
- `docs/experiments/main-benchmark/analysis/smoke/context-ablation-regex-log-20260722/warnings.json`

## Command

The run was started in tmux:

```bash
tmux new-session -d -s phase5-context-ablation 'cd /Users/danielgraviet/Desktop/projects/go-explore && bash scripts/phase5_context_ablation_smoke.sh 2>&1 | tee jobs/phase5-context-ablation-regex-log-20260722-tmux.log'
```

The script sources `.env`, runs the clean retry and branch root through Harbor/Daytona, selects one archive snapshot from the root, runs three continuation modes, writes a context-ablation manifest, and builds analysis tables.

Model:

```text
anthropic/claude-haiku-4-5-20251001
```

Selected snapshot:

```text
go-explore-regex-log__VgDNmsH-step-0
```

Selected archive entry:

- Cell key: `{/app/regex.txt}`
- Event: `file_edit`
- Score: `1.25`
- Changed files: `/app/regex.txt`
- Created at: `2026-07-22T21:04:01+00:00`

## Results

| Method | Context | Job | Solved | Tokens | Cost | Wall clock | Snapshot overhead | Restore overhead |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| `retry` | `original_task_only` | `phase5-context-ablation-regex-log-20260722-retry-seed-0-attempt-0` | 0/1 | 12054 | $0.02560250 | 88.820463s | 29.590091s | |
| `branch_root` | `original_task_only` | `phase5-context-ablation-regex-log-20260722-root-seed-0` | 0/1 | 38264 | $0.03500905 | 129.514124s | 37.000421s | |
| `full_snapshot_parent_summary` | `parent_summary` | `phase5-context-ablation-regex-log-20260722-parent-summary-snapshot-0` | 0/1 | 127274 | $0.05811875 | 194.624855s | 56.117962s | 6.850402s |
| `full_snapshot_none` | `none` | `phase5-context-ablation-regex-log-20260722-none-snapshot-0` | 0/1 | 5254 | $0.01308200 | 78.487925s | 17.756026s | 2.709465s |
| `full_snapshot_critical_parent_summary` | `critical_parent_summary` | `phase5-context-ablation-regex-log-20260722-critical-parent-summary-snapshot-0` | 0/1 | 109298 | $0.04618980 | 149.202586s | 25.973959s | 2.958764s |

Total smoke cost across the five rows was $0.177, using 292144 counted tokens including cache tokens.

Continuation reports:

- `jobs/phase5-context-ablation-regex-log-20260722-root-seed-0/continuation-report-parent_summary.json`
- `jobs/phase5-context-ablation-regex-log-20260722-root-seed-0/continuation-report-none.json`
- `jobs/phase5-context-ablation-regex-log-20260722-root-seed-0/continuation-report-critical_parent_summary.json`

All three reports recorded `any_success: false`.

## Interpretation

The result does not support treating parent-summary context as the only cause of continuation failure. If inherited context were the only major problem, `full_snapshot + none` would be expected to improve more clearly. It did not solve the task.

The token results do show that inherited context is expensive. `full_snapshot_none` used 5254 tokens, while `full_snapshot_parent_summary` used 127274 and `full_snapshot_critical_parent_summary` used 109298. This suggests that context ablation is worth keeping for cost control even though it was not enough to produce success here.

The selected snapshot was an early `/app/regex.txt` edit from a failed root. Restoring that file likely carried the child into a bad partial solution. That points to the next improvement being better snapshot selection or probe scoring, not just prompt context removal.

## Warnings And Limits

The analysis warning file contains six warnings:

- Planned token budgets are `planning_only` labels, not enforced caps.
- `repeated_setup_score` is unsupported for this analysis run because no repeated-work report was provided.

Snapshot cell metadata is now joined for the continuation rows, and restore overhead is populated from the restored jobs' Harbor `environment_setup` intervals. Snapshot overhead is recorded and complete.

This is one task, one selected snapshot, one seed, and one model. It is a useful smoke result, not paper-grade evidence.

## Validation

Completed:

```bash
bash -n scripts/phase5_context_ablation_smoke.sh
git diff --check -- scripts/phase5_context_ablation_smoke.sh
.venv/bin/python -m go_explore.cli build-analysis-tables --help
test -f docs/experiments/context-ablation-smoke-20260722.md
```
