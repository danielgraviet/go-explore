# Experiment A results

Executed 2026-08-15. Protocol:
[claim1-representation-ablation.md](claim1-representation-ablation.md).
Do not fold these rows into Experiment 2 Phase B (17/25 vs 6/25).
Aug 6 canaries are not this experiment.

Model: `anthropic/claude-haiku-4-5-20251001`. Remaining cap R=200,000 on
every child. `diagnostic_only=true`. Every arm `planned_token_cap=200000`.
Agent: `go_explore.agents.factory:SnapshotAwareTerminus2`.

Cell key: `1.0` = verifier reward 1.0; `0.0` = finished without solving;
`budget` = `AgentBudgetExhaustedError`; `DiffApplyFailed` = executor
failure (arm invalid for the 5-way comparison).

## Primary table (solve / exception)

| Task | Seed | clean | diff_only | diff_transcript | command_replay | full_snapshot |
| --- | --- | --- | --- | --- | --- | --- |
| extract-elf | 0 | budget | DiffApplyFailed | DiffApplyFailed | budget | **1.0** |
| extract-elf | 1 | budget | **1.0** | **1.0** | budget | budget |
| extract-elf | 2 | budget | budget | budget | **1.0** | budget |
| extract-elf | 3 | budget | **1.0** | **1.0** | budget | budget |
| extract-elf | 4 | budget | budget | **1.0** | budget | budget |
| regex-log | 0 | 0.0 | DiffApplyFailed | DiffApplyFailed | budget | **1.0** |
| regex-log | 1 | budget | DiffApplyFailed | DiffApplyFailed | 0.0 | 0.0 |
| regex-log | 2 | budget | DiffApplyFailed | DiffApplyFailed | 0.0 | 0.0 |
| regex-log | 3 | 0.0 | DiffApplyFailed | DiffApplyFailed | 0.0 | budget |
| regex-log | 4 | 0.0 | DiffApplyFailed | DiffApplyFailed | 0.0 | 0.0 |

## Validity

- extract-elf seed 0 diff arms are **invalid**: `parent.diff` was git usage
  text because `/app` is not a git repo. Capture was fixed afterward
  (`go_explore/snapshots/capture_diff.py`). Do not treat seed 0 as a
  complete 5-way row. clean / replay / snapshot on that seed are usable.
- regex-log diff arms are **invalid on all 5 seeds**. Captured patches
  started with a junk `diff --git a/- b/-` path and `git apply` failed.
  clean / replay / snapshot remain comparable on regex-log.
- extract-elf seeds 1–4 are complete 5-way rows (diffs applied).

## What this supports

On the four extract-elf seeds with valid diffs, a compressed start state
solved the remaining cap and full snapshot did not (seeds 1, 3, 4: diff;
seed 2: command replay). Snapshot restore did solve extract-elf seed 0
and regex-log seed 0, where the compressed file-diff arms were invalid or
unsolved.

This is **not** “full snapshots beat git diffs / replay.” If anything,
valid extract-elf rows go the other way. n is small; one model; two
tasks. Restore overhead on `full_snapshot` was ~2.2–2.8s.

## Tokens and wall clock

Source: `jobs/claim1-<task>-single-seed-<n>/representation-ablation.json`.

| Task | Seed | Arm | reward | exception | tokens | sec | restore_s |
| --- | --- | --- | --- | --- | --- | --- | --- |
| extract-elf | 0 | clean | | budget | 246594 | 146.9 | |
| extract-elf | 0 | diff_only | | DiffApplyFailed | | 13.2 | |
| extract-elf | 0 | diff_transcript | | DiffApplyFailed | | 11.5 | |
| extract-elf | 0 | command_replay | | budget | 231087 | 134.2 | |
| extract-elf | 0 | full_snapshot | 1.0 | | 84926 | 96.4 | 2.29 |
| extract-elf | 1 | clean | | budget | 221020 | 102.5 | |
| extract-elf | 1 | diff_only | 1.0 | | 34186 | 76.2 | |
| extract-elf | 1 | diff_transcript | 1.0 | | 170908 | 107.6 | |
| extract-elf | 1 | command_replay | | budget | 228526 | 106.6 | |
| extract-elf | 1 | full_snapshot | | budget | 226227 | 75.1 | 2.24 |
| extract-elf | 2 | clean | | budget | 221464 | 104.4 | |
| extract-elf | 2 | diff_only | | budget | 204874 | 91.8 | |
| extract-elf | 2 | diff_transcript | | budget | 209122 | 71.5 | |
| extract-elf | 2 | command_replay | 1.0 | | 194726 | 133.4 | |
| extract-elf | 2 | full_snapshot | | budget | 213347 | 97.4 | 2.29 |
| extract-elf | 3 | clean | | budget | 224610 | 129.4 | |
| extract-elf | 3 | diff_only | 1.0 | | 245099 | 118.7 | |
| extract-elf | 3 | diff_transcript | 1.0 | | 174281 | 95.2 | |
| extract-elf | 3 | command_replay | | budget | 228071 | 106.5 | |
| extract-elf | 3 | full_snapshot | | budget | 221888 | 122.9 | 2.49 |
| extract-elf | 4 | clean | | budget | 220735 | 108.7 | |
| extract-elf | 4 | diff_only | | budget | 223721 | 133.9 | |
| extract-elf | 4 | diff_transcript | 1.0 | | 128289 | 106.2 | |
| extract-elf | 4 | command_replay | | budget | 228433 | 100.1 | |
| extract-elf | 4 | full_snapshot | | budget | 222032 | 96.4 | 2.78 |
| regex-log | 0 | clean | 0.0 | | 27153 | 68.8 | |
| regex-log | 0 | diff_only | | DiffApplyFailed | | 18.8 | |
| regex-log | 0 | diff_transcript | | DiffApplyFailed | | 10.4 | |
| regex-log | 0 | command_replay | | budget | 214781 | 115.2 | |
| regex-log | 0 | full_snapshot | 1.0 | | 52778 | 66.0 | 2.46 |
| regex-log | 1 | clean | | budget | 215654 | 113.5 | |
| regex-log | 1 | diff_only | | DiffApplyFailed | | 15.5 | |
| regex-log | 1 | diff_transcript | | DiffApplyFailed | | 13.3 | |
| regex-log | 1 | command_replay | 0.0 | | 52545 | 62.3 | |
| regex-log | 1 | full_snapshot | 0.0 | | 8626 | 50.9 | 2.67 |
| regex-log | 2 | clean | | budget | 218311 | 143.6 | |
| regex-log | 2 | diff_only | | DiffApplyFailed | | 11.6 | |
| regex-log | 2 | diff_transcript | | DiffApplyFailed | | 13.4 | |
| regex-log | 2 | command_replay | 0.0 | | 73263 | 73.8 | |
| regex-log | 2 | full_snapshot | 0.0 | | 37348 | 72.3 | 2.84 |
| regex-log | 3 | clean | 0.0 | | 44879 | 75.1 | |
| regex-log | 3 | diff_only | | DiffApplyFailed | | 17.6 | |
| regex-log | 3 | diff_transcript | | DiffApplyFailed | | 16.7 | |
| regex-log | 3 | command_replay | 0.0 | | 35656 | 82.8 | |
| regex-log | 3 | full_snapshot | | budget | 228688 | 110.9 | 2.82 |
| regex-log | 4 | clean | 0.0 | | 4950 | 39.3 | |
| regex-log | 4 | diff_only | | DiffApplyFailed | | 11.3 | |
| regex-log | 4 | diff_transcript | | DiffApplyFailed | | 10.9 | |
| regex-log | 4 | command_replay | 0.0 | | 10033 | 68.5 | |
| regex-log | 4 | full_snapshot | 0.0 | | 138572 | 84.5 | 2.29 |
