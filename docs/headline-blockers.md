# What's Blocking the Headline Result

Working list of the real blockers found while chasing a clean "Go-Explore
raises solve rate on hard tasks for a small model" headline, based on actual
trajectory/data inspection (git-multibranch headline run + fixpilot +
rootfrac pilot), not speculation.

## 1. Budget exhaustion dominates, on both sides of the split

`AgentBudgetExhaustedError` is the majority failure mode across every task
and every method. Splitting a fixed total budget doesn't dodge this: roots
exhaust their share, and children — even with an equal or larger share of
the same total budget — exhaust theirs too. Cutting the root's share
further (`branch_root_fraction` 0.3 → 0.15) did not help; if anything it
looked slightly worse (2/5 → 1/5 on the same seeds), likely because a
starved root produces a thinner, less useful archive for children to
inherit. There isn't yet a config that reliably beats plain retry on
aggregate solve rate (headline: retry 68% vs. promising_branch 24%).

My thoughts: I think the budget framing is the issue. I imagine a student taking
a test in a single session. They can start the test, work on problems, gather
context on the test as they take it and then try to finish. This is the root task.
Then consider a different student A. He starts the test, makes some progress, and now
gets yanked away from the test. Then a new student B pops up, sits at the same spot
and has to resume. This is difficult now because student B has to use the remaining test time
but now has to catch up to speed on what student A was doing, and why it was doing it.
Trying to enter student A's thoughts while being dumped in halfway through.

## 2. False confidence — the agent submits a broken solution as done

The agent frequently declares the task complete without real verification,
or after a real check it itself misran. Terminus-2 already asks for
confirmation once before stopping, but that confirmation is a generic "are
you sure?" with no grounding in reality — a model that fooled itself once
just reaffirms the same wrong belief a second time. Seen at both root and
child level. This is the blocker the new `verify_before_complete` harness
guard (just built, pilot in progress) directly targets.

## 3. Children burn budget re-discovering how to verify, not fixing the task

A restored sandbox forces the child to re-establish ground truth before it
can do anything useful. Observed directly: `python` not on PATH, `pytest`
not installed, several turns spent working out that the real check lives
at `/tests/test.sh` before any actual debugging starts. On one trajectory,
the winning retry solved in 11 steps / 90k tokens; a child on the same task
took 26 steps / 190k tokens, and most of the gap was verification-tooling
archaeology, not task work. Partially mitigated (injected the exact
verifier path into the child's prompt), but the agent doesn't always use
the hint even when it's right there.

## 4. Verifier mismatch compounds false confidence

Related to #2 but a distinct root cause: the agent's own hand-rolled check
(e.g. running the raw pytest file directly) doesn't reproduce whatever the
official `/tests/test.sh` actually does — missing setup steps, fixtures, or
output-format handling. So the agent isn't just careless, it's sometimes
getting a genuinely different (wrong) answer than the real scored verifier.

## 5. Archive selection previously rewarded false completions

Found and fixed: a step where the agent merely *claimed* completion was
being scored by the archive selector as if it were a real passing test run
(`SnapshotEvent.VERIFIER` with no actual pass/fail data attached). That let
a root that lied about being done outrank roots with genuine partial
progress, actively selecting a worse continuation point. Fixed by no longer
treating a bare completion claim as a verification signal.

## 6. Infra fragility adds noise on top of the real signal

Two distinct issues, both found and fixed during this work:
- `prune_snapshots.py` deleted a root's snapshots as soon as *one* of its
  children had launched, not all of them — killing a not-yet-started
  second child with `DaytonaValidationError: Snapshot ... not found`.
- Assorted `EnvironmentStartTimeoutError` / `DaytonaValidationError` noise
  unrelated to the above, especially on `code-from-image`, likely from
  bulkier restored state being more fragile to fork.

Neither is a finding about the algorithm, but both make individual pilots
look worse than the mechanism actually is if not accounted for.

## 7. Some tasks give the archive too little to work with

`large-scale-text-editing` produced only 1 branch child per root instead of
the requested 2, on every seed — the archive likely didn't have enough
distinct high-quality candidate states to fill both slots. A thin archive
caps the mechanism's own optionality regardless of anything else being
right.

## Net read

Two of these (5, 6) were bugs, now fixed. Two (2, 4) are being actively
addressed (harness verifier guard, pilot in progress). Two (1, 3) are the
hardest and least resolved: the mechanism doesn't yet reliably beat blind
retry on aggregate, and even a "successful" restore still pays a real
token tax just to re-establish trust in the environment before doing any
new work.
