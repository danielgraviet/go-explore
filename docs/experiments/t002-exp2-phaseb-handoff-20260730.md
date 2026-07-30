# T002 Experiment 2 Phase B — Handoff (paused 2026-07-30)

Status: **paused mid-run, budget fix identified but not yet applied.** Nothing
is currently executing. See "Immediate next step" below.

## Where things stand

- **Experiment 1**: done, analyzed, memo written. Not part of this handoff.
- **Experiment 2 Phase A (clean screen)**: done. Report published:
  `docs/experiments/t002-exp2-screen-report.md`. Final 5-task headline set
  approved by user: `git-multibranch`, `extract-elf`,
  `custom-memory-heap-crash`, `code-from-image`, `large-scale-text-editing`.
- **Experiment 2 Phase B (headline benchmark)**: in progress, paused. Design:
  5 independent repetitions × (3 clean retries + 1 `promising_branch` root +
  2 children, `context_mode=none`) per task, `B`=500,000 as originally
  launched. **This budget is now known to be too tight — see below.**

## Why it's paused: budget is too tight at B=500,000

Once split into retry/root/child shares, B=500,000 is not enough for these
5 harder headline tasks, even though the Phase A screen (which used the
*full* B=500,000 per single clean attempt) showed reasonable solve rates.

Evidence (pooled across `extract-elf` and `code-from-image`, the two tasks
that ran to completion before this was caught):

- 47 of 56 completed jobs hit `AgentBudgetExhaustedError`.
- Those 47 had already consumed 153,000-229,000 tokens (median 183,449)
  before being cut off — above the retry share (166,667) **and** the branch
  child share (175,000).
- The 9 jobs that did solve only needed up to 128,923 tokens.

`extract-elf` was hit hardest: 0/5 roots, 0/13 retries, only 2/10
continuations solved — essentially every clean-retry attempt failed on
budget, not difficulty.

**Recommendation, not yet applied**: raise `B` to **1,000,000**. That makes
retry share 333,333, root share 300,000, child share 350,000 — all
comfortably above the 229,000 max observed exhaustion-cutoff. This mirrors
exactly how Experiment 1's B=150,000→500,000 fix was resolved and validated.

## Immediate next step (for tomorrow's agent)

1. Confirm no background jobs are running and no jobs are silently still
   executing (see "Known gotchas" below for how to check this correctly).
2. Clean up 3 orphaned Daytona sandboxes left over from stopping the batch
   (safe to stop, no local process is tracking them):
   - `git-multibranch__tiJF9wT__env`
   - `large-scale-text-editing__fPEBX6v__env`
   - `custom-memory-heap-crash__VqgadQM__env`
3. Update `docs/experiments/t002-exp2-candidate-screen-preregistration.md`
   is unaffected (it's Phase A only); the Phase B budget was never formally
   pre-registered in its own file — if writing one, record B=1,000,000 with
   the reasoning above, before any Phase B result is inspected for the
   headline claim (none have been used for that yet — the current partial
   data was diagnostic only).
4. **Wipe all `t002-exp2-headline-*` job dirs, manifests, and analysis
   dirs** (full clean restart, not a partial resume — the old B=500,000 data
   is budget-confounded and must not be mixed with new B=1,000,000 data):
   ```bash
   rm -rf jobs/t002-exp2-headline-*
   rm -f docs/experiments/main-benchmark/manifests/t002-exp2-headline-*.json
   rm -rf docs/experiments/main-benchmark/analysis/t002-exp2-headline-*
   ```
5. Relaunch all 5 lanes at B=1,000,000. Launch script template (already used
   for this batch, still on disk at `/tmp/launch_headline_task.sh` if that
   session's /tmp survives, otherwise reconstruct):
   ```bash
   uv run python -m go_explore.cli run-experiment \
     --dataset "terminal-bench@2.0" \
     --task-name "$TASK" \
     --model anthropic/claude-haiku-4-5-20251001 \
     --experiment-id "t002-exp2-headline-$TASK" \
     --job-prefix "t002-exp2-headline-$TASK" \
     --manifest-path "docs/experiments/main-benchmark/manifests/t002-exp2-headline-$TASK.json" \
     --analysis-dir "docs/experiments/main-benchmark/analysis/t002-exp2-headline-$TASK" \
     --total-token-budget 1000000 \
     --method retry --method promising_branch \
     --seed 0 --seed 1 --seed 2 --seed 3 --seed 4 \
     --n-retries 3 \
     --n-branch-continuations 2 \
     --branch-root-fraction 0.3 \
     --branch-context-mode none \
     --execute
   ```
   Run one lane per task (`$TASK` in `git-multibranch`, `extract-elf`,
   `custom-memory-heap-crash`, `code-from-image`, `large-scale-text-editing`),
   5 concurrent lanes total — matches the pre-established 5-concurrent-lane
   discipline for this project.

## Known gotchas from today (read before resuming)

- **Daytona enforces a ~100 snapshot-per-account cap.** Prune regularly with
  `uv run python3 prune_snapshots.py` (repo root) — it only deletes
  snapshots whose owning job has finished, and for branch roots specifically,
  only once their children already have local job directories. Safe to
  re-run anytime.
- **Deleting snapshots mid-run breaks any root whose children haven't
  launched yet** (the archived snapshot name they'd restore from is gone).
  If snapshots get deleted while lanes are running: stop the running lanes
  first, then check every `*-promising-branch-seed-*-root` job dir for
  `result.json` present but fewer than 2 sibling `-snapshot-*` dirs — those
  specific repetitions (root + whatever children exist) must be wiped and
  re-run. Do not touch repetitions where the root already spawned both
  children (they already restored before the deletion, so they're fine).
- **Job-level `result.json` existing does NOT mean the job is done.** Check
  `finished_at` inside it (`None` means still running) or, more simply, that
  the corresponding trial subdirectory also has its own `result.json`. A
  bare `find ... -name result.json` count is not a reliable completion
  check — this caused confusion twice today.
- **Jobs sometimes go quiet on stdout for several minutes right at the end**
  (no new log lines, no `EXIT_CODE` printed) before completing normally on
  their own. This happened twice and both times self-resolved. Don't
  kill+relaunch reflexively — check `daytona.list()` for a live sandbox
  matching the stalled trial's session id first; if it's still `STARTED` or
  `SNAPSHOTTING`, it's making progress, just wait.
- **Concurrency**: 5 lanes at a time is the established safe limit for this
  account (one Harbor `run-experiment` process per task, each internally
  sequential — n_concurrent=1 per job). Going beyond ~5-6 concurrent lanes is
  what caused the original snapshot-limit incident in Experiment 1.
- Deleting Daytona snapshots/sandboxes in bulk via the Python SDK gets
  blocked by the local permission classifier; a single targeted
  `daytona.delete(sandbox)`/`daytona.snapshot.delete(snapshot)` call
  sometimes goes through, but don't rely on it — the user has been doing
  bulk cleanup via the Daytona web UI instead.

## Reference docs

- `docs/experiments/t002-exp1-result-memo.md`, `t002-exp1-findings.md` —
  Experiment 1, done.
- `docs/experiments/t002-exp2-candidate-screen-preregistration.md` — Phase A
  design (B=500,000, correct as-is, Phase A already ran and is done).
- `docs/experiments/t002-exp2-screen-report.md` — Phase A results and the
  approved 5-task headline set.
- `tasks/phase-7-fixes/T002-run-matched-multi-seed-trials.md` — the
  governing ticket, including the paired-solve-rate primary analysis spec
  for Phase B once it completes at the corrected budget.
