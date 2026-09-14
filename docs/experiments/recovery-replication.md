# Experiment B: Recovery Replication — Pre-registration

Pre-registered 2026-08-15. Do not pool with Experiment 2 Phase B
(17/25 vs 6/25). Report paired root-fail → child-solve counts only.

## Claim under test (ledger P2)

On the two tasks where rescue already fired, how often does a child
solve after the root fails, when children are **not** launched if the
root already solved?

Prior signals (different protocols, not this experiment):

- `extract-elf` headline seeds 1–3: child recovered budget-exhausted roots
- `regex-log` n=8 after archive tie-break: 2/8 recoveries, retry 0/8, plus
  two solved-root regressions

## Fixed settings

- Tasks: `extract-elf`, `regex-log`
- Dataset: `terminal-bench@2.0`, env: `daytona`
- Agent: `go_explore.agents.factory:SnapshotAwareTerminus2`
- Model: `anthropic/claude-haiku-4-5-20251001`
- Method pair: `retry` vs `promising_branch`
- Seeds: **8** per task
- Aggregate budget B: **1,000,000** (`hard_token_limit`)
- `n_retries=3`, `n_branch_continuations=2`, `branch_root_fraction=0.3`
- `branch_context_mode=none`
- Selector: `archive_priority`
- **`--skip-children-if-root-solved`** required

## Primary outcomes

Per task × seed:

| Field | Meaning |
| --- | --- |
| retry_solved | any of the 3 retries scored 1.0 |
| root_solved | branch root scored 1.0 |
| children_launched | false if status `skipped_root_solved` |
| child_solved | any launched child scored 1.0 |
| rescued | root failed and a child solved |

Headline for this experiment is **rescued / roots that failed**, plus
retry_solved / 8 for the matched control. Do not convert to a pooled
percentage across tasks until both tasks finish.

## Exclusion rules

Same as Experiment 1: missing archive, missing lineage, non-enforced
budget, Harbor import-path bug. Infra failures labeled F8, not counted
as algorithm losses.

## Execution

Plan:

```bash
uv run python -m go_explore.cli run-experiment \
  --dataset terminal-bench@2.0 \
  --task-name extract-elf \
  --experiment-id recovery-extract-elf \
  --total-token-budget 1000000 \
  --method retry --method promising_branch \
  --seed 0 --seed 1 --seed 2 --seed 3 \
  --seed 4 --seed 5 --seed 6 --seed 7 \
  --n-retries 3 --n-branch-continuations 2 \
  --branch-root-fraction 0.3 \
  --branch-context-mode none \
  --skip-children-if-root-solved
```

Add `--execute` only when Daytona snapshotting is healthy (a `fix-git`
snapshot-aware canary creates `go-explore-*-step-*` snapshots). Repeat
with `--task-name regex-log --experiment-id recovery-regex-log`.

One task at a time. Snapshot cap ~100.

## Result memo location

`docs/experiments/recovery-replication-results.md`. Until that file
exists, do not cite a new paired rescue rate.
