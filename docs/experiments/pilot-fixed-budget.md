# Pilot Fixed-Budget Runbook

This pilot is an infrastructure check, not evidence for the research claim. It
uses one easy task to verify that the current harness can produce manifests,
archive state, continuation reports, event logs, and budget fields.

## Scope

| Field | Value |
| --- | --- |
| Date | 2026-07-21 |
| Experiment id | `pilot-fixed-budget-001` |
| Task | `fix-git` |
| Dataset | `terminal-bench@2.0` |
| Model | `anthropic/claude-haiku-4-5-20251001` |
| Agent | `go_explore.agents.factory:SnapshotAwareTerminus2` |
| Environment | Daytona |
| Fixed budget | 100,000 planned tokens |
| Budget enforcement | `planning_only` |

`fix-git` is intentionally easy. It is useful for harness validation because it
is bounded and consistently produces archive artifacts, but it has almost no
headroom for measuring Go-Explore lift.

Candidate follow-up tasks from `docs/task-selection.md`:

| Task | Why |
| --- | --- |
| `git-leak-recovery` | Git inspection state should make snapshot reuse meaningful. |
| `regex-log` | Likely has repeated inspect/edit/test loops. |
| `openssl-selfsigned-cert` | Bounded artifact generation and deterministic verifier. |

## Dry-Run Fixed-Budget Manifest

The fixed-budget planner was run as a dry run:

```bash
mkdir -p docs/experiments
uv run python -m go_explore.cli plan-fixed-budget \
  --dataset terminal-bench@2.0 \
  --task-name fix-git \
  --env daytona \
  --model anthropic/claude-haiku-4-5-20251001 \
  --agent-import-path go_explore.agents.factory:SnapshotAwareTerminus2 \
  --experiment-id pilot-fixed-budget-001 \
  --job-prefix pilot-fix-git \
  --manifest-path docs/experiments/pilot-fixed-budget-manifest.json \
  --total-token-budget 100000 \
  --method single \
  --method retry \
  --method random_branch \
  --method promising_branch \
  --seed 0 \
  --n-retries 2 \
  --n-branch-continuations 1 \
  --branch-root-fraction 0.3 \
  --snapshot go-explore-fix-git__8LivXBM-step-3
```

Artifact:

- `docs/experiments/pilot-fixed-budget-manifest.json`

Manifest contents:

| Method | Jobs | Planned budget |
| --- | --- | --- |
| `single` | 1 clean run | 100,000 tokens |
| `retry` | 2 clean attempts | 50,000 tokens each |
| `random_branch` | root + 1 continuation | 30,000 root, 70,000 child |
| `promising_branch` | root + 1 continuation | 30,000 root, 70,000 child |

The two branch continuations use the known snapshot
`go-explore-fix-git__8LivXBM-step-3` so the manifest can contain concrete child
commands. In a real online pilot, branch child rows should initially be
`pending_root_archive` until the root run creates an archive.

## Live Snapshot Smoke

The live root run used:

```bash
set -a; source .env; set +a
export PATH="$HOME/.local/bin:$PATH"
export PYTHONPATH="$PWD"
harbor run \
  --env daytona \
  --jobs-dir jobs \
  --n-attempts 1 \
  --n-concurrent 1 \
  --dataset terminal-bench@2.0 \
  --include-task-name fix-git \
  --n-tasks 1 \
  --model anthropic/claude-haiku-4-5-20251001 \
  --job-name e2e-p3-t002-root \
  --export-traces \
  --agent-import-path go_explore.agents.factory:SnapshotAwareTerminus2
```

Artifacts:

- `jobs/e2e-p3-t002-root/result.json`
- `jobs/e2e-p3-t002-root/archive.json`
- `jobs/e2e-p3-t002-root/events.jsonl`
- `jobs/e2e-p3-t002-root/continuation-report.json`
- `jobs/e2e-p3-t002-root/start-state-plan.json`

Validation:

```bash
uv run python -m go_explore.cli summarize-job jobs/e2e-p3-t002-root
```

Result:

```text
job_dir: jobs/e2e-p3-t002-root
trials: 1/1
errors: 0
mean: 1.0
- fix-git__8LivXBM: pass task=fix-git reward=1.0 exception=None
```

The root archive has 3 cells:

| Cell | Snapshot | Score | Times selected |
| --- | --- | --- | --- |
| `<test_run>` | `go-explore-fix-git__8LivXBM-step-3` | 3.0 | 1 |
| `{_includes/about.md}` | `go-explore-fix-git__8LivXBM-step-5` | 1.25 | 0 |
| `<command>` | `go-explore-fix-git__8LivXBM-step-0` | 0.0 | 0 |

The event log includes:

- 4 `snapshot_created` events
- 1 `snapshot_selected` event
- 1 `continuation_started` event

The selected snapshot event recorded:

| Field | Value |
| --- | --- |
| `selector_mode` | `archive_priority` |
| `selector_reasons` | `priority=3`, `score=3`, `times_selected=0` |
| `cell_key` | `<test_run>` |
| `snapshot_name` | `go-explore-fix-git__8LivXBM-step-3` |

## Start-State Plan Smoke

The start-state planner was run with:

```bash
uv run python -m go_explore.cli plan-start-state-baselines \
  jobs/e2e-p3-t002-root \
  --from-archive \
  --selector-mode random \
  --selector-seed 7 \
  --max-snapshots 1 \
  --job-prefix e2e-p3-t002-plan \
  --manifest-path jobs/e2e-p3-t002-root/start-state-plan.json
```

Artifact:

- `jobs/e2e-p3-t002-root/start-state-plan.json`

The manifest contains:

| Start state | Context mode | Executor status |
| --- | --- | --- |
| `clean` | `original_task_only` | `ready` |
| `diff_only` | `original_task_only` | `manifest_only` |
| `full_snapshot` | `parent_summary` | `ready` |

`diff_only` is only scaffolded. The manifest records
`jobs/e2e-p3-t002-root/parent.diff`, but no executor applies that diff yet.

## Live Continuation Smoke

The live continuation used archive-priority selection:

```bash
set -a; source .env; set +a
export PATH="$HOME/.local/bin:$PATH"
export PYTHONPATH="$PWD"
uv run python -m go_explore.cli continue-from-snapshots \
  jobs/e2e-p3-t002-root \
  --from-archive \
  --selector-mode archive_priority \
  --max-snapshots 1 \
  --job-prefix e2e-p3-t002-cont \
  --execute
```

Artifacts:

- `jobs/e2e-p3-t002-cont-snapshot-0/result.json`
- `jobs/e2e-p3-t002-root/continuation-report.json`

Validation:

```bash
uv run python -m go_explore.cli summarize-job jobs/e2e-p3-t002-cont-snapshot-0
```

Result:

```text
job_dir: jobs/e2e-p3-t002-cont-snapshot-0
trials: 1/1
errors: 0
mean: 1.0
- fix-git__yqXhN2q: pass task=fix-git reward=1.0 exception=None
```

Continuation report summary:

| Field | Root | Continuation |
| --- | --- | --- |
| Reward | 1.0 | 1.0 |
| Total tokens | 29,725 | 13,371 |
| Cost USD | 0.0311717 | 0.019683 |
| Duration seconds | 228.512973 | 148.865059 |
| Start state | clean root | `full_snapshot` |
| Context mode | original task/root context | `parent_summary` |

Total observed model cost for this smoke was about `0.0508547` USD.

## Did The Harness Work?

The snapshot continuation harness worked end to end for this task:

1. Harbor ran a Daytona root job through the snapshot-aware agent.
2. The root job wrote `archive.json`.
3. The root job wrote snapshot lifecycle events.
4. The start-state planner produced clean, diff-only, and full-snapshot rows.
5. Archive-priority selection chose the expected `<test_run>` snapshot.
6. The continuation restored from the selected Daytona snapshot and passed.
7. The continuation report included budget and start-state metadata.
8. The fixed-budget planner generated a dry-run manifest with method names,
   seeds, budget splits, and commands.

This does not show that snapshot branching improves solve rate. `fix-git` is
too easy: the root and continuation both solved it.

## Missing Fields And Broken Assumptions

| Gap | Current state | Next move |
| --- | --- | --- |
| Runtime token enforcement | Manifest records budget splits, but Harbor/model calls are not capped by this planner. | Add runtime budget controls only if Harbor/model APIs expose a clean hook. |
| Diff-only execution | `diff_only` is `manifest_only`; no patch application executor exists. | Implement or explicitly defer a clean diff-apply executor. |
| Command/test event materialization | Live `events.jsonl` contains snapshot events, but not normalized `command_executed`, `test_run`, or `dependency_installed` events. | Materialize extracted ATIF signals into event logs or analysis inputs. |
| Repeated-work tables | P3-T004 can compute repeated-work JSON, but it is not joined into CSV analysis tables yet. | P3-T006 should join repeated-work metrics into run summaries. |
| Snapshot overhead fields | `snapshot_overhead_seconds` and `restore_overhead_seconds` are still `unknown`. | Persist timing from snapshot creation and restore paths. |
| Task difficulty | The smoke used an easy task. | Run 1-3 medium tasks after the analysis table path exists. |

## Next Experiment

The next useful pilot should run the same fixed-budget dry-run shape on one or
two medium tasks from `docs/task-selection.md`, starting with
`git-leak-recovery` or `regex-log`.

Before running that pilot, finish P3-T006 so the output includes analysis-table
rows with method, budget, solve status, lineage, and repeated-work metrics.
