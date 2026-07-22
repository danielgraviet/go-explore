# T006: Viability Analysis Memo

## Goal

Write the decision memo that says whether sandbox snapshot continuation is viable enough to continue as a research direction.

## Context

This replaces the earlier paper-fill-in goal. The memo should report what happened, including negative results, and decide what engineering or research path is justified.

## Scope

Write `docs/experiments/viability-analysis.md` answering:

- Does continuation produce unique successes beyond clean retry?
- Does continuation reduce tokens, cost, or wall time?
- Which snapshot cells help or hurt?
- Does `context_mode=none` outperform or underperform `critical_parent_summary`?
- Did any `parent_summary` diagnostic arm justify keeping it in future runs?
- Which failures are implementation bugs versus research limitations?

## Out of Scope

- Do not rerun benchmark jobs.
- Do not rewrite `docs/essay.md` unless the user explicitly asks.
- Do not hide negative results.

## Suggested Starting Points

- Full viability analysis tables.
- Pilot memo.
- `docs/experiments/failure-case-audit.md`
- `docs/experiments/context-ablation-smoke-20260722.md`

## Acceptance Criteria

- Every headline number links to a generated table or job artifact.
- The memo states supported, weakened, and refuted hypotheses.
- The memo recommends one of: continue, narrow scope, redesign selector/probes, or stop.
- The memo lists concrete next tickets if the direction continues.

## Validation

Cross-check every numerical claim against `run-summary.csv`, `task-summary.csv`, and continuation reports.

## Notes / Open Questions

The acceptable outcome can be a no-go decision. The goal is to learn whether the approach is viable, not to force the original hypothesis to be true.
