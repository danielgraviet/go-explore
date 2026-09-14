# Experiment E: Env-progress ablation — Pre-registration

Pre-registered 2026-08-31, before any scored env-progress seed.
Do not pool with Experiment 2 Phase B (17/25 vs 6/25) or with
Experiment A/B on Terminal-Bench.

Terminal-Bench is file-centric. Ledger S19 showed compressed start
states beating full snapshot on extract-elf. This experiment asks the
Daytona-shaped question: **when progress lives in the machine, does a
full snapshot beat `git apply` of the same checkpoint?**

## Claim under test (ledger S21, after the memo exists)

On `staged-service-repair`, same planted checkpoint, same remaining
token cap:

- `clean` starts from the task image
- `diff_only` starts from the image plus `parent.diff`
- `full_snapshot` restores the Daytona snapshot (`context_mode=none`)

Possible outcomes, all publishable:

- snapshot >> diff and clean: machine state is the missing unit
- snapshot ≈ compressed: even an env-progress task does not justify VM restore
- snapshot < compressed: inherited machine state is a trap (F2)

## Inclusion test (must pass on the canary before scored seeds)

A planted checkpoint is valid only if all four hold:

1. `diff_only` either fails to apply or applies and the **hidden lot
   code is still missing** (verifier reward 0). The lot exists only in
   `/var/lib/inventory/store.db`, not in `/app` and not in the
   instruction.
2. `full_snapshot` restore lineage is real (Harbor used
   `snapshot_template_name=<planted snapshot>`).
3. `clean` must reinstall and recreate the warehouse; it cannot read
   the lot from the image.
4. The task is not ceiling (`fix-git`) and not a single answer-file
   basin (`regex-log`).

If (1) fails (diff arm recovers the lot), stop. Do not hunt a third
task to reverse the finding. Report that result.

## Arms

| Arm | `start_state_type` | `context_mode` |
| --- | --- | --- |
| clean | `clean` | `original_task_only` |
| diff_only | `diff_only` | `original_task_only` |
| full_snapshot | `full_snapshot` | `none` |

No transcript or command-replay arms. The question is snapshot vs patch
vs scratch.

## Fixed settings

- Task path: `tasks/env-progress/staged-service-repair`
- Env: `daytona`
- Agent: `go_explore.agents.factory:SnapshotAwareTerminus2`
- Model: `anthropic/claude-haiku-4-5-20251001`
- Remaining cap R: **200,000** tokens (`hard_token_limit`) on every arm
- Checkpoint: deterministic plant
  (`scripts/plant_env_progress_checkpoint.py`), built from the task
  Dockerfile via Daytona `Image.from_dockerfile` (Harbor 0.19 no longer
  logs `Using prebuilt image:`). Not a live agent root
- Seeds: 1 canary, then **5** scored seeds (0–4) if the canary passes
  the inclusion test
- `parent.diff` captured from the planted snapshot via
  `capture_parent_diff`
- Snapshot retention 4; children `snapshot_policy=none`; prune after
  each seed (`--prune`) so the account stays under ~100 snapshots

## Primary outcomes

Per seed: reward, exception, tokens, wall clock, restore overhead.
Lead with paired per-seed solve, not a pooled %.

Canary also records whether HTTP `/items/WIDGET-7` returns the planted
lot on snapshot vs diff vs clean.

## Exclusion rules

Invalid: plant snapshot missing, `parent.diff` is git usage text,
Harbor `--agent terminus-2` combined with the import path, restore
`DaytonaValidationError`. Report invalid seeds; do not hide them.

## Execution

```bash
# Canary (1 seed)
uv run python -u scripts/run_publication_experiments.py env-canary --prune

# Scored (seeds 0–4; skips completed)
uv run python -u scripts/run_publication_experiments.py env --prune
```

## Result memo

[docs/experiments/env-progress-ablation-results.md](env-progress-ablation-results.md)
(2026-08-31). Ledger **S21**.
