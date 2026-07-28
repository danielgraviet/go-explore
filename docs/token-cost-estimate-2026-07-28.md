# Token Cost Estimate

Date: 2026-07-28

This note estimates **model-provider token cost only** for the planned paper
work in `docs/essay.md`. It excludes sandbox, Daytona, and other infra costs.

## Assumptions

- Small model: Claude Haiku 4.5
- Medium model: Claude Sonnet 4.6
- Large model: Claude Opus 4.8
- Claim 1 track: `clean` vs `diff_only` vs `full_snapshot`
- Claim 2 track: `single`, `retry`, `random_branch`, `promising_branch`
- Base planning unit: 1 seed unless otherwise noted

## Current Public Pricing

- Haiku 4.5: about `$1 / 1M input tokens` and `$5 / 1M output tokens`
- Sonnet 4.6: about `$3 / 1M input tokens` and `$15 / 1M output tokens`
- Opus 4.8: about `$5 / 1M input tokens` and `$25 / 1M output tokens`

Sources:

- [Claude Haiku 4.5 pricing](https://www.anthropic.com/claude/haiku)
- [Claude Sonnet 4.6 pricing](https://www.anthropic.com/news/claude-sonnet-4-6)
- [Claude Opus 4.8 pricing](https://www.anthropic.com/news/claude-opus-4-8)

## Empirical Anchors From This Repo

Recent benchmark runs in this repository give the following rough token
shapes:

- `qemu-startup` primary: about **7.1M tokens** across the completed rows
  (`single`, `retry`, `random_branch`, `promising_branch`)
- Smoke tasks: about **0.2M to 3.0M tokens per task**, depending on task
  shape and retry depth

Relevant local artifacts:

- [qemu-startup primary run summary](./experiments/main-benchmark/analysis/phase4-primary-qemu-startup-001/run-summary.csv)
- [smoke analysis folders](./experiments/main-benchmark/analysis/smoke/)

## Planning Estimate

The following is a conservative planning range for one full pass of the paper
work under a single model size.

| Scope | Rough tokens | Haiku 4.5 | Sonnet 4.6 | Opus 4.8 |
| --- | ---: | ---: | ---: | ---: |
| Claim 1 pilot, 6 tasks, 3 start states, 1 seed | 10M-25M | $10-$40 | $35-$120 | $55-$200 |
| Claim 2 main benchmark, 49 tasks, 4 arms, 1 seed | 65M-100M | $70-$160 | $220-$480 | $360-$800 |
| Claim 1 + Claim 2 combined | 75M-125M | $80-$200 | $255-$600 | $415-$1,000 |

These ranges assume:

- one seed first,
- no extra best-of-N expansion,
- no major retried infrastructure failures,
- normal agent output lengths for coding tasks,
- prompt caching only where the harness naturally reuses context.

## Cost Multipliers

The biggest cost drivers are:

- number of seeds,
- number of retry attempts,
- branch continuations per root,
- model size,
- whether a task is setup-heavy and produces long prompts or long outputs.

Useful rule of thumb:

- doubling seeds roughly doubles token cost,
- adding best-of-N roughly multiplies the relevant arm cost by `N`,
- Opus is about 5x Haiku on input cost and 5x on output cost.

## Practical Budgeting Guidance

If the goal is to keep the paper affordable while still getting strong
evidence:

1. Run the Claim 1 pilot first on Haiku or Sonnet.
2. Run Claim 2 on Haiku first, then promote only the most informative slice to
   Sonnet or Opus.
3. Do not start with full 3-model coverage across every harness variant unless
   the pilot results are already strong enough to justify it.

## Spend Control Plan

Target: keep total provider spend around `$1,500` or lower for the full
experimental sweep.

Recommended execution order:

1. Start with a single-seed pilot on Haiku across the smallest useful slice of
   `clean`, `diff_only`, and `full_snapshot`.
2. Use that pilot to identify the highest-signal harness/task combinations.
3. Expand breadth on Haiku before adding more seeds or more expensive models.
4. Promote only a narrow confirmatory subset to Sonnet.
5. Use Opus only for the smallest set of cases where the marginal evidence is
   worth the cost.
6. Keep branch fanout, retry counts, and best-of-N low until the cheaper sweep
   has already shown a clear signal.

Practical guardrails:

- Prefer one seed first for each new condition.
- Avoid running all model sizes across all harness variants at once.
- Treat `qemu-*` and other VM-heavy tasks as high-cost outliers and keep their
  coverage narrow.
- If the first Haiku pass is ambiguous, promote a subset rather than rerunning
  the entire matrix on a larger model.

## Notes

- The benchmark runs in this repo already show that a few tasks can jump above
  1M tokens per task.
- `qemu-startup` is a good warning case: it is not representative of the cheap
  end of the task set.
- Final cost should be recalculated once the exact task list and seed counts are
  fixed.
