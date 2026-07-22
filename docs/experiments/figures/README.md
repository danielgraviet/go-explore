# Figure Tables

These artifacts are generated from normalized analysis tables.

| Figure | Status | Interpretation |
| --- | --- | --- |
| `solve_rate_by_method` | `ready` | Requires completed task-summary rows. |
| `cost_per_solved_task` | `ready` | Requires solved tasks with cost fields. |
| `unique_task_overlap` | `ready` | Requires at least one solved task. |
| `branch_success_by_snapshot_event_type` | `ready` | Requires continuation run rows joined with snapshot cell keys. |
| `promising_vs_random_branch_lift` | `ready` | Requires paired random_branch and promising_branch task outcomes. |
| `repeated_setup_work` | `ready` | Requires repeated-work metrics joined into run rows. |
| `snapshot_overhead` | `ready` | Requires persisted snapshot/restore overhead fields. |
| `oracle_gap` | `deferred_no_observed_signal` | Requires oracle_branch rows or precomputed oracle labels. |

When the benchmark has only planned manifests and no completed run
summaries, evidence-dependent figures are intentionally marked as
deferred rather than plotted from missing data.
