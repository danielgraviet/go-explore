# Handoff: preflight_verification eval + primary-set prep, 2026-07-27

Written for whoever picks this up tomorrow. Read this first. Related prior
doc: `docs/handoff-2026-07-24-child-solve-rate.md` (now corrected, see
below) for the T004 background this work builds on.

## Where things stand

All code from today is committed and pushed to `main` (commits `c5ba6b3`,
`4a225f0`). Nothing is staged or uncommitted.

### 1. `preflight_verification` context mode - built, tested, evaluated

New context mode alongside `none`/`resume_notice`/`parent_summary`/etc: runs
the task's own verifier against the restored sandbox *before* the child
agent's first turn, and hands it the real pass/fail result as a fact
("9 of 11 tests passed. Failing: test_numpy_version...") instead of a vague
"look before you leap" nudge like `resume_notice`.

- Implementation: `go_explore/snapshots/preflight.py` (new module -
  `run_preflight_verification()`, uploads the task's real `tests/` dir,
  execs the real `test.sh`, parses `ctrf.json`), wired into
  `go_explore/agents/snapshot_agent.py` (`_apply_context_mode` now takes
  `environment`, branches on `preflight_verification`). Plumbed through
  `continuations.py`, `cli.py` (3 argparse choice lists), `fixed_budget.py`.
  218 tests passing, including a regression test for a real bug I found and
  fixed mid-eval (see below).
- **Not** wired into `--clean-context-mode` (no state to verify against on a
  clean start) or the legacy sync `perform_task` path (no async
  `BaseEnvironment` there - documented limitation, always degrades to a
  fallback message on that path, not a bug to fix).
- Real bug found and fixed during evaluation: status was originally derived
  from the shell command's exit code, but the task's `test.sh` convention
  always ends with `echo ... > reward.txt`, whose exit code is always 0
  regardless of whether pytest passed. Fixed to derive status from the CTRF
  test counts instead. Regression test:
  `test_run_preflight_verification_trusts_ctrf_over_misleading_exit_code`
  in `tests/test_preflight.py`.

**Eval results** (all against known validated-tier archive snapshots,
i.e. snapshots where the archived state actually passed its own tests):

| comparison | none | resume_notice | preflight_verification |
| --- | --- | --- | --- |
| regex-log, single validated snapshot (9/9 tests) | fail (blind overwrite) | success | success |
| build-cython-ext, single validated snapshot (18/18 tests) | fail (blind `git clone` over restored repo) | fail (inspected first, but silently upgraded numpy, broke `test_numpy_version`) | **11/11, reward 1.0, no numpy regression** |
| kv-store-grpc, single validated snapshot | success | — | success (control: doesn't hurt when nothing to destroy) |
| regex-log, n=8 `promising_branch` pilot | 2/8 recovered (t004b) | 2/8 recovered (t004c) | **3/8 recovered** (t009, see below) |

t009 (n=8, `--branch-context-mode preflight_verification`, directly
comparable to t004b/t004c) result data is on disk but **not yet combined
into one analysis table** - it was run split across 5 parallel shards
(`docs/experiments/main-benchmark/manifests/t009/shard-{,d,e,f,g}.json`,
same under `analysis/t009/`) for wall-clock reasons. Raw per-seed rewards
already extracted and reported in-conversation: seeds 0, 1, 5 succeeded;
2, 3, 4, 6, 7 failed. Someone should run `build-analysis-tables` across all
5 shards' job dirs to get one real `run-summary.csv`/`task-summary.csv`
before citing this number anywhere formal.

n=8 is still a small sample (1-recovery difference over baseline). Directionally
positive and consistent with every single-snapshot case, not yet strong
statistical evidence on its own.

### 2. Doc correction

`docs/handoff-2026-07-24-child-solve-rate.md` had an inaccurate "8/8, no
exceptions" claim about `resume_notice`'s inspect-before-overwrite behavior.
Corrected in place: one child (seed-4) never ran a single command and
hallucinated task completion; real count is 6/8 confirmed via structured
tool-call logs, 7/8 if you count a child that used an older embedded-format
log. This is committed now (was "left staged" earlier, since pushed).

### 3. Recurring regression pattern - now seen on 3 task families

The "successful root, destroyed by child" regression (root passes, its
`none`-mode branch continuation fails) has now been observed on regex-log
(original T004 case), and today reproduced fresh on
`openssl-selfsigned-cert` during the smoke run below. This is no longer an
edge case worth a footnote - it looks like a property of `none`-mode
branching in general. Relevant to the primary-run decision below.

### 4. Task-set validation

`docs/experiments/task-set.md` (43 primary + 6 smoke tasks, written
2026-07-21) was re-validated today against a fresh `list-cached-tasks` pull:
all 60 unique task references still match the current local cache exactly
(same difficulty, same timeouts). No drift. This list is ready to use
as-is - do not regenerate it from scratch.

### 5. Smoke subset - 5 of 6 tasks executed today, 1 still running

Manifests existed for all 6 smoke tasks but only `fix-git`/`regex-log` had
ever actually been run (from an earlier session). Today launched the other
4 in parallel tmux windows (session `phase6-build-cython`, still alive
locally as of this writing):

| task | result | notes |
| --- | --- | --- |
| `git-leak-recovery` | 10/10 succeeded | Too easy, no headroom - matches the doc's existing note about `fix-git`. Smoke-only, not primary-set evidence. |
| `openssl-selfsigned-cert` | single✓, retry 2/5, random_branch root✓+child✓, **promising_branch root✓ but child✗** | Fresh instance of the regression pattern in #3 above. |
| `sqlite-db-truncate` | **0/10 failed** (one job hit a `DaytonaNotFoundError` infra blip, the other 9 ran clean with zero exceptions and still all failed) | See decision below - kept in primary set anyway per existing policy. |
| `qemu-startup` | **still running** as of this handoff (window `smoke-qemu` in the `phase6-build-cython` tmux session; 6/12 jobs done - single + 5 retries, branch methods not started yet) | Check this first tomorrow. |

## Decisions made today (with the user, explicit)

1. **`sqlite-db-truncate` stays in the primary 43** despite 0/10 in smoke.
   The task-set doc has an explicit rule: "Do not replace tasks because one
   method solved or failed them" - written specifically to prevent
   outcome-based cherry-picking. Let the real primary-run seeds decide, not
   an n=1 smoke result. Do not swap this out without raising it again first.
2. **The primary 43-task run should use `--branch-context-mode
   preflight_verification`**, explicitly passed on the command, **not** by
   changing the shared `DEFAULT_BRANCH_CONTEXT_MODE` constant in
   `fixed_budget.py` (still `"none"`) - that constant is also used by
   viability pilots, which have their own documented reason to default to
   `none`. Only the primary-run invocation should override it.
3. **EC2 (`Go-Explore` host in `~/.ssh/config`, currently being paused by
   the user) is not to be used yet.** Wait for explicit "ready" before
   SSHing in or launching anything there. When that happens, the plan is to
   drive experiments over SSH the same tmux-based way as today's local runs.

## What to do next (priority order)

1. **Check on `smoke-qemu`** (tmux session `phase6-build-cython`, window
   name `smoke-qemu`) - it was still running when this was written. Confirm
   it finishes clean, then the full 6-task smoke subset is done and the
   harness is validated end to end.
2. **Build `best-of-N` as a method**, before the primary run, not after.
   It's one of the three named baselines in `docs/essay.md`'s Claim 2
   (single, retry, best-of-N) and doesn't exist at all right now -
   `ExperimentMethod` in `fixed_budget.py` is only
   `Literal["single", "retry", "random_branch", "promising_branch"]`.
   Structurally it's closest to `retry` plus a selection step - the
   oracle-labels/selector machinery in `go_explore/snapshots/selectors.py`
   is relevant prior art. This is real implementation work (comparable
   scope to `preflight_verification`) - use the same plan-first approach
   (EnterPlanMode, Explore the codebase, write a plan file) rather than
   diving straight into code.
3. **Once EC2 is confirmed ready**, launch the 43-task primary set there
   with `--branch-context-mode preflight_verification`, per decision #2
   above. This is the actual Claim 2 headline-number experiment from
   `docs/essay.md` - nothing at this scale has been run yet in this
   project's history.
4. **Claim 1 has zero evidence collected, ever, in this project.** The
   essay's other core claim (full snapshots beat diff-only/transcript/
   command-replay representations) hasn't been tested at all - everything
   done so far, including all of today's work, has been tuning *inside*
   Claim 2's `promising_branch` arm. Infra partially exists:
   `plan-start-state-baselines` already supports `clean`/`diff_only`/
   `full_snapshot` start states. `command_replay` as a fourth condition
   does not exist and would need to be built. A `clean` vs `diff_only` vs
   `full_snapshot` ablation on 5-6 tasks could start immediately without
   waiting on that. This is unclaimed ground worth prioritizing once (2)
   and (3) are moving - possibly a good parallel track for EC2's
   round-the-clock capacity rather than a strictly sequential step.

## Housekeeping

- tmux session `phase6-build-cython` has ~15 windows accumulated from
  today (t007/t008/t009 experiment shards, smoke tasks). Most are finished
  and idle (dropped to an interactive shell after `DONE_EXIT_N`). Safe to
  `tmux kill-session -t phase6-build-cython` once `smoke-qemu` is confirmed
  done and you've pulled any numbers you need from the panes - job results
  themselves are all persisted under `jobs/`, nothing is lost by killing
  the session.
- `docs/experiments/main-benchmark/analysis/t009/shard-*` need combining
  into one table (see #1 above) before the n=8 preflight_verification
  number gets cited anywhere beyond this conversation.
- `.env` already has `GO_EXPLORE_SNAPSHOT_REMOTE_LIMIT=3` set - the earlier
  KeyError from a stale env is resolved and should not recur.
