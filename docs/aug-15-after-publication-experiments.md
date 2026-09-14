# Aug 15 — after the publication experiments

Give this file to a coding agent when the live A/B runs are done (or if they stalled).

Today is **2026-08-15**. Snapshotting works again. Claude credits are available. Daytona account cap is **~100 snapshots total** (templates count). Baseline non-Go-Explore snapshots were **31**. Hard abort at **90**. Do not pass `--prune` unless the live count is about to hit that cap; per-seed prune deleted the extract-elf seed 0 checkpoint and blocked recapture.

## What was launched

Driver: `scripts/run_publication_experiments.py`

| Stage | Command | Status at handoff |
| --- | --- | --- |
| A canary | `uv run python -u scripts/run_publication_experiments.py a-canary` | Done. extract-elf seed 0. |
| A | `uv run python -u scripts/run_publication_experiments.py a` | Started 13:45 UTC. Skips seeds that already have `jobs/claim1-<task>-single-seed-<n>/representation-ablation.json`. |
| B | `uv run python -u scripts/run_publication_experiments.py b` | **Not started.** Run this only after A finishes. Same skip logic via `docs/experiments/main-benchmark/analysis/recovery-<task>-seed-<n>/execution-report.json`. |

Roots snapshot with `GO_EXPLORE_SNAPSHOT_REMOTE_LIMIT=4`. Retries and children use `snapshot_policy=none`. Check `--env` / `.env` for `DAYTONA_API_KEY` and `ANTHROPIC_API_KEY`. Model: `anthropic/claude-haiku-4-5-20251001`. Agent: `go_explore.agents.factory:SnapshotAwareTerminus2`. Never also pass `--agent terminus-2`.

Check progress:

```bash
set -a; source .env; set +a
export PYTHONPATH="$PWD" PATH="$HOME/.local/bin:$PATH"
uv run python scripts/run_publication_experiments.py count
ls jobs/claim1-*-single-seed-*/representation-ablation.json
ls docs/experiments/main-benchmark/analysis/recovery-*/execution-report.json
```

If A died mid-seed, rerun `a` (completed seeds skip). If B was never started, run `b`. If the snapshot count is ≥90, stop and tell the user; do not prune unless they ask.

## Frozen numbers — do not touch

Experiment 2 Phase B headline stays **retry 17/25 (68%) vs promising_branch 6/25 (24%)**. Do not revise, average, or pool A/B into that table. Source: `docs/experiments/t002-exp2-headline-results-memo.md`. Ledger: `docs/claim-ledger.md` S5.

Aug 6 checkpoint-diagnostic canaries are not evidence (snapshotting was broken).

## Experiment A — fill this first

Protocol: `docs/experiments/claim1-representation-ablation.md`  
Empty memo: `docs/experiments/claim1-representation-ablation-results.md`

Tasks `extract-elf`, `regex-log`; seeds 0–4; arms clean / diff_only / diff_transcript / command_replay / full_snapshot; remaining cap 200k.

Per seed, read `jobs/claim1-<task>-single-seed-<n>/representation-ablation.json` (and the Harbor `result.json` under each arm job). Fill the 5-way table: reward, exception, tokens, wall clock. Lead with paired per-seed solves, not a pooled %.

**extract-elf seed 0 is only partly valid.** Root budget-exhausted. clean and command_replay budget-exhausted. **full_snapshot solved (reward 1.0)**. Both diff arms are `DiffApplyFailed` because `parent.diff` was git usage text (`/app` is not a git repo). That capture bug is fixed in `go_explore/snapshots/capture_diff.py` for later seeds. Label seed 0 diff arms invalid; do not hide them. Do not treat seed 0 as a complete 5-way row.

Claim 1 / ledger **P1 is citable only after this memo has real rows.** Possible outcomes (all publishable): snapshot >> compressed, snapshot ≈ compressed, or snapshot < compressed.

## Experiment B — fill this second

Protocol: `docs/experiments/recovery-replication.md`  
Empty memo: `docs/experiments/recovery-replication-results.md`

Same two tasks; 8 seeds; retry (3) vs promising_branch (1 root + 2 children); B=1e6; `branch_root_fraction=0.3`; `context_mode=none`; `--skip-children-if-root-solved`.

Report **rescued / failed-roots**, not a pooled % with 17/25. `rescued` = root failed and a child scored 1.0. If the root solved, children should be `skipped_root_solved`. Unlock ledger **P2** only after this memo has real rows.

## After both memos exist

1. Update `docs/claim-ledger.md` P1/P2 from the memos. Do not promote anything listed under **Not supported**.
2. Optionally refresh `docs/blog/daytona-snapshots-as-search-states.md` and `docs/whitepaper/returning-to-development-states.md` with the new supported sentences only.
3. Do not change `docs/essay.md` headline thesis: returning is real; returning is not enough; under a matched budget independent retries currently solve more Terminal-Bench tasks.
4. Index: `docs/publication.md`.

## Do not

- Rewrite 17/25 vs 6/25.
- Pool regex-log 2/8 or these A/B rows into the headline.
- Claim snapshots beat retry.
- Claim Claim 1 from seed 0 alone, or from Aug 6 canaries.
- Force-push, commit, or open a PR unless asked.
- Print `.env` secrets.
