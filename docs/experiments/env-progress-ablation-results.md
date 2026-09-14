# Experiment E results

Executed 2026-08-31. Protocol:
[env-progress-ablation.md](env-progress-ablation.md).
Do not fold these rows into Experiment 2 Phase B (17/25 vs 6/25) or
into Terminal-Bench Experiments A/B.

Model: `anthropic/claude-haiku-4-5-20251001`. Remaining cap R=200,000 on
every arm. `diagnostic_only=true`. Agent:
`go_explore.agents.factory:SnapshotAwareTerminus2`.

Planted checkpoint: `go-explore-staged-service-repair__plant-step-0`
(deterministic plant, not a live agent root). Harbor restore lineage
verified: every `full_snapshot` plan carried
`snapshot_template_name=go-explore-staged-service-repair__plant-step-0`.
`parent.diff` is empty (the quantity migration was already committed in
`/app`; the lot code is only in `/var/lib/inventory/store.db`). Empty
apply is valid; it does not recover the lot.

Cell key: `1.0` = verifier reward 1.0; `0.0` = finished without solving;
`budget` = `AgentBudgetExhaustedError`.

## Primary table (solve / exception)

| Seed | clean | diff_only | full_snapshot | notes |
| --- | --- | --- | --- | --- |
| 0 | 0.0 | 0.0 | **1.0** | canary; inclusion passed |
| 1 | 0.0 | 0.0 | 0.0 | snapshot restored DB without quantity; agent did not migrate |
| 2 | 0.0 | 0.0 | **1.0** | |
| 3 | 0.0 | budget | **1.0** | |
| 4 | 0.0 | 0.0 | **1.0** | |

Paired solves: snapshot **4/5**, `diff_only` **0/5**, `clean` **0/5**.

## Inclusion test

1. `diff_only` never recovered the hidden lot (0/5; seed 3 budget-exhausted).
   The lot is not in `parent.diff`.
2. Restore lineage is real (snapshot name in every snapshot-arm Harbor command).
3. `clean` never read the lot from the image (0/5).
4. Not ceiling (`fix-git`) and not a single answer-file basin (`regex-log`).
   Seed 1 shows leftover work after restore.

If `diff_only` had recovered the lot, this experiment would have stopped.
It did not.

## What this supports

On this staged service-repair task, the reusable unit is the live
machine: a warehouse SQLite outside `/app` plus a venv. A git apply of
the checkpoint is not the checkpoint. Snapshot restore solved more often
and with fewer tokens than `clean` or `diff_only` at the same remaining
cap.

This is **not** a rewrite of 17/25, and it is not “snapshots beat retry
on Terminal-Bench.” n=5 seeds, one custom task, one model.

Seed 1 is a handoff miss, not a restore miss: the planted DB was present
(`sku`/`name`/`lot`, no `quantity`); health later passed; the agent did
not apply `002_add_quantity.sql`. Harbor-observed restore overhead on
snapshot arms was ~2.8–3.5s.

## Tokens and wall clock

Source: `jobs/env-progress-checkpoint-root/representation-ablation-seed-<n>.json`.

| Seed | Arm | reward | exception | tokens | sec | restore_s |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | clean | 0.0 | | 74033 | 107.7 | |
| 0 | diff_only | 0.0 | | 163850 | 151.3 | |
| 0 | full_snapshot | 1.0 | | 22724 | 97.6 | 3.36 |
| 1 | clean | 0.0 | | 101982 | 120.9 | |
| 1 | diff_only | 0.0 | | 35664 | 78.7 | |
| 1 | full_snapshot | 0.0 | | 32651 | 104.8 | 3.54 |
| 2 | clean | 0.0 | | 25634 | 73.9 | |
| 2 | diff_only | 0.0 | | 173179 | 150.7 | |
| 2 | full_snapshot | 1.0 | | 41416 | 104.9 | 3.15 |
| 3 | clean | 0.0 | | 49345 | 260.5 | |
| 3 | diff_only | | AgentBudgetExhaustedError | 215966 | 172.3 | |
| 3 | full_snapshot | 1.0 | | 33526 | 74.9 | 2.82 |
| 4 | clean | 0.0 | | 35566 | 80.3 | |
| 4 | diff_only | 0.0 | | 48961 | 93.4 | |
| 4 | full_snapshot | 1.0 | | 21348 | 62.4 | 2.90 |

Oracle bake of the same task (Harbor `--agent oracle`) scored 1.0 before
the scored seeds; that row is solvability only, not an ablation arm.
