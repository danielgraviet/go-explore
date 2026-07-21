# Figure Tables

These artifacts are generated from normalized analysis tables.

| Figure | Status | Interpretation |
| --- | --- | --- |
| `solve_rate_by_method` | `deferred_no_task_summary` | Requires completed task-summary rows. |
| `cost_per_solved_task` | `deferred_no_task_summary` | Requires solved tasks with cost fields. |
| `unique_task_overlap` | `deferred_no_task_summary` | Requires at least one solved task. |
| `branch_success_by_snapshot_event_type` | `deferred_no_run_summary` | Requires continuation run rows joined with snapshot cell keys. |
| `promising_vs_random_branch_lift` | `deferred_no_task_summary` | Requires paired random_branch and promising_branch task outcomes. |
| `repeated_setup_work` | `deferred_no_run_summary` | Requires repeated-work metrics joined into run rows. |
| `snapshot_overhead` | `deferred_no_run_summary` | Requires persisted snapshot/restore overhead fields. |
| `oracle_gap` | `deferred_no_task_summary` | Requires oracle_branch rows or precomputed oracle labels. |

When the benchmark has only planned manifests and no completed run
summaries, evidence-dependent figures are intentionally marked as
deferred rather than plotted from missing data.
