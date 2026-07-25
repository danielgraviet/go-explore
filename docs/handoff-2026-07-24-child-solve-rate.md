# Handoff: child solve-rate work, 2026-07-24

Written for whoever picks this up after the weekend. Read this first, then
`docs/t001-t005-phase6-fixes-results.md` for the detailed T001-T005 history
if you need it. `tasks/phase-6-fixes/` has one ticket file per fix.

## Where things stand

All of T001-T005 are done and merged to `main` (see
`docs/t001-t005-phase6-fixes-results.md` for full detail):

- **T001**: fixed the archive's tie-break bug (later edits to the same
  file were being discarded in favor of the first attempt). Merged.
- **T002/T003**: verified T001 via replay and a live run. Done.
- **T004**: comparative pilot. First pass (regex-log + sqlite-db-truncate,
  n=3) was a null result (0 solves everywhere). Follow-up n=8 pass,
  regex-log only, `context_mode=none`: **retry 0/8, branch 2/8** — the
  first real evidence of "root fails, child restores and finishes."
  Also caught and fixed a stale validator bug (`failure_symptom` wasn't
  accepted by `fixed_budget.py`). Merged.
- **T005**: confirmed `build-cython-ext`'s earlier `n_snapshots_created: 0`
  was transient Daytona infra, not a policy bug. No code change. Done.
- **T006**: still correctly blocked/deferred.

## Child trace analysis (the part in progress)

After the T004 n=8 result, I read all 8 child trajectories against their
parent archives to understand why children succeed or fail. Finding:
**every child, on its first action, overwrote the restored target file
without reading it first** - including a case (seed-0) where the parent's
restored snapshot was already a validated 9/9-passing solution, which the
child destroyed and failed to reproduce. Root cause: `context_mode=none`
gives the child zero indication the sandbox isn't empty (no instruction
augmentation happens at all for that mode).

From that, four candidate fixes were identified, to be built one branch
at a time:

1. **(built, merged)** Add a cheap, content-free `resume_notice` context
   mode: one static sentence telling the child to inspect existing state
   before changing it. No parent narrative/reasoning - kept comparable to
   `none` so it isolates whether *that specific* blind-overwrite behavior
   is fixable. Implementation: `go_explore/agents/snapshot_agent.py`
   (`_augment_instruction_resume_notice`, `_apply_context_mode`), plus
   `continuations.py`, `fixed_budget.py`, `cli.py` for the new mode
   choice. Tests added in `tests/test_snapshot_agent.py` and
   `tests/test_cli.py`. Merged via `dg/resume-orientation-notice`.

2. **(not started)** Differentiate the nudge by snapshot tier: if the
   selected archive entry is validated (`tests_failed==0 and
   tests_passed>0`), tell the child to verify before rewriting; if it's
   merely a partial `file_edit`, no such warning is warranted (seed-1 in
   the n=8 pilot shows restarting from a partial attempt works fine as-is).

3. **(not started)** Automatic pre-flight verification: run the task's own
   check against the restored state before the agent's first turn, and
   hand the result to the agent as a fact, rather than relying on the
   agent choosing to look.

4. **(not started, methodological)** Test on a task where code/state reuse
   is more central than a single-artifact task like `regex-log` (e.g.
   `build-cython-ext`, `kv-store-grpc`), since every regex-log child
   discarded the parent's actual file content regardless of outcome - the
   only thing reliably reused was environment scaffolding, not code.

Separately, unticketed: the seed-0/seed-2 "successful root, failed child"
regression pattern (continuing past an already-solved root can make things
worse, not just waste tokens) deserves its own look at some point.

## In-progress: evaluating fix #1

Running an n=8 `regex-log` `promising_branch` pilot with
`--branch-context-mode resume_notice`, directly comparable to the earlier
`none`-mode run (`docs/experiments/main-benchmark/analysis/t004b/branch/`,
2/8 recovered). Command used:

```bash
.venv/bin/python -m go_explore.cli run-experiment \
  --dataset terminal-bench@2.0 --task-name regex-log \
  --experiment-id t004c-regex-log-resume-notice --job-prefix t004c-regex-log-resume-notice \
  --model anthropic/claude-haiku-4-5-20251001 --total-token-budget 100000 \
  --method promising_branch \
  --seed 0 --seed 1 --seed 2 --seed 3 --seed 4 --seed 5 --seed 6 --seed 7 \
  --n-branch-continuations 1 --branch-context-mode resume_notice \
  --manifest-path docs/experiments/main-benchmark/manifests/t004c/branch.json \
  --analysis-dir docs/experiments/main-benchmark/analysis/t004c/branch \
  --execute
```

### Final result (run completed - all 8 chains finished)

| seed | root | child |
|---|---|---|
| 0 | fail | fail |
| 1 | fail | **success** |
| 2 | fail | fail |
| 3 | fail | fail |
| 4 | fail | fail |
| 5 | fail | **success** |
| 6 | fail | fail |
| 7 | fail | fail |

**2/8 recovered - the same count as the `none` baseline
(`docs/experiments/main-benchmark/analysis/t004b/branch/run-summary.csv`).**
Raw solve-rate did not improve in this sample.

But the fix did demonstrably work as designed. Checked all 4 available
child trajectories (seeds 0-3) plus seed-1's in detail: every single
child's first action in this run was `ls -la` (inspect first), and
seed-1's child went on to `cat /app/regex.txt` (read the restored file)
before deciding to rewrite it. In the `none` baseline, **zero** of 8
children ever read the restored file before overwriting it - it was
always the first action, no exceptions. So the notice changed behavior
exactly as intended, 8/8.

**Why the aggregate number didn't move**: in this particular n=8 draw,
*every root failed* - none reached a validated, passing state. The
specific harm `resume_notice` targets (a child destroying an
already-correct solution, as seen in the `none` run's seed-0) requires a
root that actually got somewhere first. With no validated-state roots in
this sample, that failure mode had no chance to occur either way, so this
run couldn't test the thing it was built to fix - it could only show that
the new behavior (inspect first) doesn't *hurt* when the restored state
is actually broken, which it didn't.

## What to do next (this is the real open question, not a re-run)

A plain n=8 re-roll of the same setup is unlikely to reliably produce
validated-state roots either - regex-log's root solve rate for haiku is
low (~20% per earlier phase4 data), and only some fraction of those
solves will have a captured `test_run`/`validated_progress` snapshot
archived at all. Two options, pick one:

1. **Targeted test**: instead of sampling random roots, deliberately
   construct/select cases where the archived snapshot is validated-tier
   (`tests_failed==0 and tests_passed>0` on the archive entry - see
   `jobs/t004b-regex-log-branch-promising-branch-seed-0-root/archive.json`
   for a real example of this shape) and only test continuations from
   those. This directly measures whether `resume_notice` prevents the
   destroy-a-good-solution regression, which is the actual claim.
2. **Bigger n**: run enough seeds that a handful of validated-tier roots
   show up naturally, then look at just that subset. Costs more but needs
   no special selection logic.

Recommend option 1 - cheaper and directly targeted. Once you have that
comparison, decide whether to build fix #2 (tiered nudge: stronger
"verify before rewriting" language specifically when the snapshot is
validated-tier, vs. no such warning for partial-tier - see the
"Child trace analysis" section above) or fix #3 (automatic pre-flight
verification) next.

## Housekeeping

- `docs/experiments/main-benchmark/{manifests,analysis}/t004c/` are
  currently untracked (not committed) - commit them on their own branch
  per the established one-branch-per-fix pattern (see
  `dg/resume-orientation-notice` for the code this evaluates). A small
  `dg/resume-notice-eval-results` branch for just the results/docs is
  probably cleanest, matching how `dg/branch-context-mode-validator-fix`
  carried T003-T005's results separately from the code fixes.
- The run this time actually did survive to completion despite not using
  `tmux` (contrary to the caution earlier in this doc) - but that was not
  guaranteed, and the next long run should still use the runbook's tmux
  pattern (`docs/runbook.md`, "Run the paid pilot in tmux") rather than
  relying on that again.
