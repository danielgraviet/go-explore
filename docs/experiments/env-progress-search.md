# Experiment F: Env-progress search — Pre-registration

Pre-registered 2026-09-11, before any scored env-progress search seed.
Do not pool with Experiment 2 Phase B (17/25 vs 6/25), Experiment A/B
on Terminal-Bench, or Experiment E (S21 representation ablation).

Experiment E asked whether a Daytona snapshot of the warehouse machine
beats a git patch of the same checkpoint. It did (snapshot 4/5, diff
0/5, clean 0/5). That is a **representation** result from a planted
start, not a search comparison.

This experiment asks the missing matched-budget question: **once both
methods start from that saved machine, does promising-branch beat
retry?**

## Claim under test (ledger S22, after the memo exists)

On `staged-service-repair`, same planted Daytona snapshot as the start
template for **every** retry attempt and **every** branch root:

- `retry`: three independent attempts from the planted snapshot
- `promising_branch`: one root from the planted snapshot, then up to
  two children restored from mid-run snapshots of that root
  (`skip-if-root-solved`)

Possible outcomes, all publishable:

- branching wins: Daytona search looks useful on this game; 17/25 still
  stands on Terminal-Bench
- both win (dual ceiling): the saved computer was enough; branching did
  not add much. Stop. Do not invent a harder task
- retry still wins: Daytona's win on this task is saving the table, not
  the search algorithm

## Fair-start rule (must hold on the canary)

Do **not** start either arm from the empty task image. The hidden lot
lives only in `/var/lib/inventory/store.db` and was planted by us. A
clean start cannot recover it except by guessing; that would make retry
lose for a dumb reason.

Both arms start from
`snapshot_template_name=go-explore-staged-service-repair__plant-step-0`
(the Experiment E plant). Children then restore from **root** snapshots,
not from the plant.

A canary is valid only if:

1. The plant snapshot is still live on the Daytona account.
2. Every retry attempt and the branch root Harbor command includes
   `snapshot_template_name=<plant>`.
3. No job is launched with `--agent terminus-2` in addition to the
   snapshot-aware import path.
4. The run is not an infrastructure failure (`DaytonaValidationError`,
   missing archive, Harbor import-path bug). Infra-invalid canaries are
   rerun, not scored, and do not unlock a second custom task unless the
   plant itself is broken.

## Ceiling stop rule

Experiment E snapshot solves often finished in ~21k–41k tokens. Retry
×3 from the same plant may both go 5/5.

After the **1-seed practice race**:

- If **both** retry and promising_branch solve seed 0, **stop**. Do not
  run seeds 1–4. Publish: the planted snapshot was a sufficient start
  template; this protocol does not identify a search advantage.
- If the canary is infra-invalid, fix and rerun the canary. Do not
  build a second game because the first was too easy.
- Otherwise run five scored seeds (0–4), skipping seed 0 if it already
  completed.

## Fixed settings

- Task path: `tasks/env-progress/staged-service-repair`
- Env: `daytona`
- Agent: `go_explore.agents.factory:SnapshotAwareTerminus2` only
- Model: `anthropic/claude-haiku-4-5-20251001`
- Methods: `retry` vs `promising_branch`
- Seeds: 1 canary (seed 0), then **5** scored seeds (0–4) if the canary
  is not dual-ceiling
- Aggregate budget B: **600,000** (`hard_token_limit`)
- `n_retries=3`, `n_branch_continuations=2`, `branch_root_fraction=0.3`
- `branch_context_mode=none`
- Selector: `archive_priority`
- `--skip-children-if-root-solved` required
- Start snapshot: reuse Experiment E plant
  (`jobs/env-progress-checkpoint-root`, trial
  `staged-service-repair__plant`). Do not replant unless the snapshot is
  gone
- Snapshot retention 4 on roots. Retries and children use
  `snapshot_policy=none`. Do not `--prune` the plant while later seeds
  still need it

B=600,000 matches three Experiment E remaining caps (3 × 200k). Root
share is 180k; children share the rest. That is enough for the E
snapshot solves, which is why the ceiling stop exists.

## Primary outcomes

Per seed:

| Field | Meaning |
| --- | --- |
| retry_solved | any of the 3 retries scored 1.0 |
| root_solved | branch root scored 1.0 |
| children_launched | false if status `skipped_root_solved` |
| child_solved | any launched child scored 1.0 |
| rescued | root failed and a child solved |
| branch_solved | root_solved or child_solved |

Lead with paired per-seed solves, not a pooled % with 17/25 or S21.

## Exclusion rules

Invalid: plant snapshot missing, Harbor `--agent terminus-2` combined
with the import path, restore `DaytonaValidationError`, missing
archive. Report invalid seeds; do not hide them. Label infra as F8, not
as an algorithm loss.

## Execution

```bash
# Confirm the plant is still live
uv run python -u scripts/run_publication_experiments.py count

# Practice race (1 seed)
uv run python -u scripts/run_publication_experiments.py env-search-canary

# Scored (seeds 0–4; skips completed; refuses if canary was dual-ceiling)
uv run python -u scripts/run_publication_experiments.py env-search
```

## Result memo

[docs/experiments/env-progress-search-results.md](env-progress-search-results.md)
(2026-09-11). Dual-ceiling canary; scored seeds not run. Ledger **S22**.
