# Regex-Log R3 Smoke Audit

## Summary

`phase4-smoke-regex-log-r3-001` was a useful negative smoke result. The runner completed successfully and produced analysis tables, continuation reports, and event logs. Scratch retry solved `regex-log` on 2 of 5 attempts, while both branch methods solved 0 of 3 runs.

This does not show that snapshot continuation is inherently worse than retry. It shows that the current combination of full-snapshot restore, `parent_summary` context, and archive selection did not improve this task.

Primary artifacts:

- `docs/experiments/main-benchmark/analysis/smoke/regex-log-r3/run-summary.csv`
- `docs/experiments/main-benchmark/analysis/smoke/regex-log-r3/task-summary.csv`
- `docs/experiments/main-benchmark/analysis/smoke/regex-log-r3/warnings.json`
- `jobs/phase4-smoke-regex-log-r3-random-branch-seed-0-root/continuation-report.json`
- `jobs/phase4-smoke-regex-log-r3-promising-branch-seed-0-root/continuation-report.json`

## Method Outcomes

| Method | Runs | Solved | Total tokens | Cost | Snapshot overhead |
| --- | ---: | ---: | ---: | ---: | ---: |
| `single` | 1 | 0 | 283250 | $0.07628845 | 87.787526s |
| `retry` | 5 | 2 | 1048805 | $0.33795870 | 640.034026s |
| `random_branch` | 3 | 0 | 589378 | $0.18634985 | 353.214789s |
| `promising_branch` | 3 | 0 | 498598 | $0.18226615 | 330.233343s |

Across all result files, the run used about $0.7829 and 2420031 total counted tokens, including cache tokens.

## Per-Run Outcomes

| Job | Role | Start state | Context | Reward | Outcome | Exception |
| --- | --- | --- | --- | ---: | --- | --- |
| `phase4-smoke-regex-log-r3-single-seed-0` | single | clean | original_task_only | 0.0 | fail | |
| `phase4-smoke-regex-log-r3-retry-seed-0-attempt-0` | retry_attempt | clean | original_task_only | 1.0 | success | |
| `phase4-smoke-regex-log-r3-retry-seed-0-attempt-1` | retry_attempt | clean | original_task_only | 0.0 | fail | |
| `phase4-smoke-regex-log-r3-retry-seed-0-attempt-2` | retry_attempt | clean | original_task_only | 0.0 | fail | |
| `phase4-smoke-regex-log-r3-retry-seed-0-attempt-3` | retry_attempt | clean | original_task_only | 1.0 | success | |
| `phase4-smoke-regex-log-r3-retry-seed-0-attempt-4` | retry_attempt | clean | original_task_only | 0.0 | fail | |
| `phase4-smoke-regex-log-r3-random-branch-seed-0-root` | root | clean | original_task_only | 0.0 | agent_error | AgentTimeoutError |
| `phase4-smoke-regex-log-r3-random-branch-seed-0-snapshot-0` | continuation | full_snapshot | parent_summary | 0.0 | fail | |
| `phase4-smoke-regex-log-r3-random-branch-seed-0-snapshot-1` | continuation | full_snapshot | parent_summary | 0.0 | fail | |
| `phase4-smoke-regex-log-r3-promising-branch-seed-0-root` | root | clean | original_task_only | 0.0 | fail | |
| `phase4-smoke-regex-log-r3-promising-branch-seed-0-snapshot-0` | continuation | full_snapshot | parent_summary | 0.0 | fail | |
| `phase4-smoke-regex-log-r3-promising-branch-seed-0-snapshot-1` | continuation | full_snapshot | parent_summary | 0.0 | fail | |

The only solved runs were retry attempts 0 and 3.

## Continuation Selections

| Method | Child job | Snapshot | Cell key | Selector | Reward |
| --- | --- | --- | --- | --- | ---: |
| `random_branch` | `phase4-smoke-regex-log-r3-random-branch-seed-0-snapshot-0` | `go-explore-regex-log__y4NVaLf-step-11` | `{/tmp/test_findall.pl}` | random | 0.0 |
| `random_branch` | `phase4-smoke-regex-log-r3-random-branch-seed-0-snapshot-1` | `go-explore-regex-log__y4NVaLf-step-0` | `{/app/regex.txt}` | random | 0.0 |
| `promising_branch` | `phase4-smoke-regex-log-r3-promising-branch-seed-0-snapshot-0` | `go-explore-regex-log__ZnUYp6i-step-0` | `{/app/regex.txt}` | archive_priority | 0.0 |
| `promising_branch` | `phase4-smoke-regex-log-r3-promising-branch-seed-0-snapshot-1` | `go-explore-regex-log__ZnUYp6i-step-7` | `{/tmp/test.py}` | archive_priority | 0.0 |

All four continuations restored a full Daytona snapshot and used `context_mode=parent_summary`. None solved the task.

## Infrastructure Versus Policy

The runner and continuation machinery worked:

- tmux/asciinema setup succeeded in every completed job.
- root jobs produced archives and event logs.
- branch jobs restored specific `snapshot_template_name` values.
- continuation reports recorded parent snapshot lineage.
- analysis tables were written at `docs/experiments/main-benchmark/analysis/smoke/regex-log-r3/`.

The main infrastructure exception was `AgentTimeoutError` in the `random_branch` root. That root still produced snapshots and both planned continuations ran. The repeated Daytona websocket `CancelledError` messages were ignored cleanup callbacks after Harbor had already written results; they should not be interpreted as failed trials.

The important research/policy failure is different: branch continuations ran from inherited states and still produced reward 0.0.

## Evidence For Inherited-State Or Context Failure

Sampled continuation trajectories show children orienting around inherited files and prior-work summaries rather than starting independently.

Relevant artifacts:

- `jobs/phase4-smoke-regex-log-r3-promising-branch-seed-0-snapshot-0/regex-log__5GrwTzW/agent/trajectory.json`
- `jobs/phase4-smoke-regex-log-r3-promising-branch-seed-0-snapshot-1/regex-log__dyvVERt/agent/trajectory.json`
- `jobs/phase4-smoke-regex-log-r3-random-branch-seed-0-snapshot-0/regex-log__kDAsEZf/agent/trajectory.json`
- `jobs/phase4-smoke-regex-log-r3-random-branch-seed-0-snapshot-1/regex-log__fKQncbf/agent/trajectory.json`

Observed patterns:

- Children inspected or repaired `/app/regex.txt` from the parent state.
- Children reasoned from a prior-attempt summary before independently validating the task.
- Several children performed local Perl or shell checks and concluded the regex was correct, but the verifier still returned 0.0.
- The selected snapshots were tied to generic file-edit cells such as `{/app/regex.txt}`, `{/tmp/test.py}`, or `{/tmp/test_findall.pl}` rather than a verified-success signal.

This is consistent with a "wrong solution basin" failure: restoring a snapshot preserves useful setup, but it also preserves incorrect intermediate work. The `parent_summary` prompt may make that state more persuasive by telling the child what was already tried.

## Hypotheses For Follow-Up

1. `parent_summary` can hurt when the parent root failed. It may imply useful progress and cause the child to trust wrong files or wrong local tests.
2. Full snapshots can preserve harmful task state. For `regex-log`, an incorrect `/app/regex.txt` is sticky; children may repair around it instead of considering a fresh formulation.
3. Archive scoring is too generic. File edits and discovery steps are not enough to identify promising regex snapshots without stronger validation/probe signals.
4. The current benchmark is not strict fixed-budget evidence. Rows report `budget_enforcement=planning_only`, and actual token counts exceeded the planned budgets.
5. Restore overhead is still unknown in the analysis rows. Snapshot overhead is recorded, but continuation restore overhead is not yet measured.

## Limitations

This is one task, one model, one seed, and one smoke configuration. It is enough to justify corrective tickets, but not enough to estimate the general value of Go-Explore-style continuation.

The run also includes `SnapshotAwareTerminus2` for scratch baselines, so retry rows created snapshots even though they did not fork from them. That is acceptable for this smoke, but future comparisons should decide whether scratch baselines should use snapshot-aware logging or a lighter agent.

The budget fields should be read as planning metadata, not enforcement. Any paper-grade claim needs either real budget enforcement or explicit planning-only labeling in all summaries.
