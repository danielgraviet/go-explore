# Phase 1 Continuation Benchmark

## Goal

Phase 1 keeps Terminal-Bench scoring honest while testing Go-Explore behavior.

The root Harbor job is still a normal single attempt. If that attempt fails,
Terminal-Bench records it as a failure. Continuation branches are separate Harbor
jobs that restore from Daytona snapshots created during the root attempt. We then
write our own lineage report that answers whether any branch solved the task.

## Why This Shape

Harbor does not currently group multiple restored branches under one native
Terminal-Bench attempt. Treating branches as separate Harbor jobs avoids changing
benchmark semantics while still giving us the data we need:

- which root trial produced the snapshot,
- which snapshot was used as the restore point,
- which continuation job ran from that snapshot,
- whether any continuation received reward `1.0`.

This means the benchmark result and Go-Explore result are intentionally separate:

- Terminal-Bench root attempt: pass/fail for the original run.
- Go-Explore continuation report: pass/fail across restored branches.

## Implementation

The continuation runner uses Harbor's Daytona environment kwarg:

```text
--ek snapshot_template_name=<snapshot-name>
```

Harbor's Daytona environment checks whether that snapshot exists and is active,
then creates the continuation sandbox from it.

Code entry points:

- `go_explore.continuations.harbor_config_from_job`: reconstructs the original
  Harbor dataset/task/agent/model shape from `jobs/<root>/config.json`.
- `go_explore.continuations.plan_snapshot_continuations`: builds one Harbor
  command per snapshot and records parent lineage.
- `go_explore.continuations.run_continuation_plans`: runs the continuation jobs
  and writes a JSON report.
- `go-explore continue-from-snapshots`: CLI surface for dry-run and execution.

## Example

Dry-run first:

```bash
go-explore continue-from-snapshots \
  jobs/daytona-hard-task-root \
  --job-prefix phase1-hard-task \
  --max-snapshots 3
```

Run the branches:

```bash
go-explore continue-from-snapshots \
  jobs/daytona-hard-task-root \
  --job-prefix phase1-hard-task \
  --max-snapshots 3 \
  --execute
```

By default, the report is written to:

```text
jobs/<root>/continuation-report.json
```

## Current Limitations

- Continuation branches are not a native Terminal-Bench multi-branch attempt.
- Snapshot selection is simple ordering plus `--max-snapshots`; ranking comes
  later.
- The root job must have a usable Harbor `config.json`.
- If no explicit `--snapshot` is passed, the CLI queries Daytona for snapshots
  matching `go-explore-<trial-name>-step-`.
