# Headline Analysis Plan (Experiment 2 Phase B)

Written 2026-07-31, while `t002-exp2-headline-*` (5 tasks, `B=1,000,000`,
`branch_context_mode=preflight_verification`) was still running. Governs
how the run's results get reported once complete — written before the run
finishes so the analysis isn't shaped by which numbers come in.

## Core principle: do not change methodology mid-run

The current design (matched retry/root/child token shares, fixed `B`,
pre-registered task list) is the cleanest comparison available. Any
adjustment made after seeing partial results — budget reallocation,
early-stop branching, different root fractions — must not be folded into
this run's headline number, even if it would produce better solve rates.
Doing so blends two different mechanisms into one reported result and
reads as post-hoc tuning to anyone auditing the methodology. New
mechanisms are explicit, separately labeled follow-up experiments (see
"Deferred, not abandoned" below), run later on the same task set for
comparability.

## Primary analysis: paired per-seed, not aggregate solve rate

Lead with the paired comparison already specified in
`tasks/phase-7-fixes/T002-run-matched-multi-seed-trials.md`: for each seed,
did the `promising_branch` root fail, and if so, did a child solve it?

This is the direct evidence for the mechanism (environment/context transfer
rescuing a specific failure), and it's legible at small n in a way an
aggregate percentage isn't. Report it as a table: task, seed, root outcome,
child outcomes, recovered y/n. Example already on hand from mid-run
inspection: `docs/early-singal-child-solve-extract-elf.md` (3 of 3
completed `extract-elf` seeds recovered by a child after root failure).

Aggregate solve-rate deltas (retry vs. promising_branch, pooled across
seeds) are secondary — report with the actual counts (e.g. "8/26") rather
than only a percentage, given n is small enough that percentages alone
overstate precision.

## Report budget exhaustion honestly, as a finding, not hide it

`AgentBudgetExhaustedError` rates observed mid-run (all at `B=1,000,000`,
after the budget was already raised once from 500k):

| Task | Finished | Budget-exhausted | Rate |
| --- | --- | --- | --- |
| git-multibranch | 16 | 8 | 50% |
| extract-elf | 26 | 16 | 62% |
| custom-memory-heap-crash | 15 | 13 | 87% |
| code-from-image | 20 | 13 | 65% |
| large-scale-text-editing | 17 | 14 | 82% |

State this upfront in the writeup as a limitation: even at the raised
budget, most failures on 2 of 5 tasks are budget exhaustion, not reasoning
failure. This preempts the "did you just pick easy tasks" objection and is
itself a citable finding about task difficulty vs. Haiku's effective
per-share budget under this split.

Also disclose the screening rule plainly: headline tasks were retained
because they fell in the 20-80% solve-rate band at the screening stage
(`docs/experiments/t002-exp2-screen-report.md`) — standard practice to
avoid ceiling/floor effects, but must be stated as selection criteria, not
presented as a random task sample.

## Deferred, not abandoned: budget-reallocation follow-ups

Ideas raised during this run that could plausibly reduce budget-exhaustion
waste and increase recovery rate, explicitly out of scope for the current
headline number:

- branch before the root exhausts its full share (stall/no-progress
  trigger instead of running root to its budget cap or completion) —
  highest-leverage candidate, since roots currently burn their entire
  allocation even when clearly stuck before any child gets a chance;
- smaller `--branch-root-fraction` (currently 0.3), trading root budget for
  child budget outright;
- reallocating some retry budget into more children per root, if retry
  solve rate turns out to be at or below child solve rate;
- task-conditional `B` instead of one flat budget across all 5 headline
  tasks, given the exhaustion-rate spread above.

Each of these is a candidate for a separate, explicitly labeled experiment
(e.g. "Experiment 3") run after this one closes, on the same 5-task set for
comparability — not a revision to this run's design or numbers.

## Model choice: Haiku is load-bearing, not a placeholder

All headline runs use `anthropic/claude-haiku-4-5-20251001`. This is an
intentional scope decision, not "the cheap option we settled for" — state
it that way in the writeup, not apologetically.

- Go-Explore's core value proposition is rescuing runs under a fixed,
  tight token budget. A weaker model hitting budget exhaustion on 50-87%
  of attempts (see budget-exhaustion table above) is exactly the regime
  where restart-from-good-state should matter most. A stronger model that
  mostly solves tasks single-shot would have little budget pressure to
  rescue from, and the effect would likely look smaller — not more
  convincing.
- State the claim's scope precisely: "Go-Explore improves solve rate under
  a fixed, tight token budget for a cost-efficient model where budget
  exhaustion is the dominant failure mode," not "Go-Explore improves agent
  performance" in general. This is a true, defensible, still-interesting
  claim, and it preempts the "does this generalize to stronger models"
  objection by answering it before it's asked rather than implying
  generality that hasn't been tested.
- The cost angle is part of the motivation, not just a budget constraint on
  this project: cheap models are exactly where teams want test-time-compute
  techniques, since retrying with a bigger model is the alternative
  they're trying to avoid.

**Deferred generalization check, kept deliberately small**: do not run a
second full 5-task headline set on a stronger model (Fable, Opus) — it
would multiply cost and reintroduce the same task-filtering problem, since
a stronger model's 20-80% solve-rate band would likely retain a different
set of tasks entirely. Instead, as a follow-up, run 1-2 seeds on the
task with the clearest recovery signal (`extract-elf`, see
`docs/early-singal-child-solve-extract-elf.md`) on a stronger model, as a
qualitative robustness spot-check: does the recovery mechanism still fire
when the model rarely exhausts budget, or does the effect disappear as
expected. Report as a secondary observation, not a competing headline
claim.

State model tier as an explicit limitation alongside task count and n=5
seeds: single model tier tested; generalization to higher-capability
models is future work.

## Reference docs

- `tasks/phase-7-fixes/T002-run-matched-multi-seed-trials.md` — governing
  ticket, paired-solve-rate primary analysis spec.
- `docs/experiments/t002-exp2-screen-report.md` — task screening and
  selection criteria for the 5 headline tasks.
- `docs/experiments/t002-exp2-phaseb-handoff-20260730.md` — why `B` was
  raised from 500k to 1,000,000.
- `docs/early-singal-child-solve-extract-elf.md` — mid-run worked example
  of the paired recovery pattern on `extract-elf`.
