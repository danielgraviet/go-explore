# T006: Evaluate Continuation Context Modes

## Goal

Run a fixed-parent study to determine which existing child-context mode works
best with a restored Go-Explore sandbox. Compare snapshot-only continuation,
skeptical parent-summary continuation, and verifier-grounded continuation from
the **same selected parent snapshots**.

This study selects the primary context mode for the adapted Go-Explore method;
it is not the headline clean-retry versus branching benchmark.

## Context

Full snapshot restoration and child memory transfer are separable mechanisms:

- `none`: restored sandbox only;
- `resume_notice`: restored sandbox plus a neutral inspect-before-modify
  notice;
- `critical_parent_summary`: restored sandbox plus a skeptical, bounded parent
  trajectory summary;
- `preflight_verification`: restored sandbox plus the result of running the
  task's real verifier and parsing its CTRF output before the child starts.

`critical_parent_summary` does **not** run the verifier. Conversely,
`preflight_verification` does not inject the parent trajectory summary. The
study measures these existing modes separately before introducing a combined
mode.

Use the following pre-registered tasks. Their clean-screen solve rates are
neither ceiling-level nor zero for the current Haiku configuration:

| Task | Clean solve rate | Category |
| --- | --- | --- |
| `git-multibranch` | 2/3 (67%) | service |
| `extract-elf` | 2/3 (67%) | debugging |
| `custom-memory-heap-crash` | 1/3 (33%) | debugging |
| `code-from-image` | 1/3 (33%) | artifact-heavy |
| `large-scale-text-editing` | 1/3 (33%) | artifact-heavy |

Relevant references:

- `go_explore/snapshots/preflight.py`
- `go_explore/agents/snapshot_agent.py`
- `go_explore/continuations.py`
- `docs/continuation-context-modes.md`
- `docs/handoff-2026-07-27-preflight-verification-and-primary-set.md`
- `tasks/phase-7-fixes/T001-enfore-token-budget.md`
- `tasks/phase-7-fixes/T002-run-matched-multi-seed-trials.md`

## Study Design

### Parent Fixtures

- Run 3 independent root trajectories per task with the same model, task
  timeout, snapshot policy, selector, and root token cap.
- For each root, choose one eligible snapshot using a pre-registered selector
  and record its snapshot name, cell/stage, score, step, and lineage.
- The root is a shared fixture for the child-context comparison. Do not run a
  different root or select a different snapshot for each context mode.
- If no eligible snapshot, archive/events, or restore proof exists, mark that
  fixture invalid for every mode. Do not replace it after child outcomes are
  seen.

### Child Context Arms

From each valid selected snapshot, launch one child for each mode:

1. `none` — snapshot-only baseline;
2. `resume_notice` — low-cost structural handoff control;
3. `critical_parent_summary` — skeptical parent-memory handoff;
4. `preflight_verification` — verifier-grounded restored-state handoff.

Every sibling child must use the same snapshot, model, task timeout, child
token cap, and agent configuration except for `context_mode`. Run the four
children as separate Harbor jobs and preserve full continuation lineage.

This is a fixed-parent child ablation. The root's cost is shared to hold state
constant, so it must not be presented as an equal-total-budget comparison
against clean retry. T002 is the experiment that evaluates the selected mode
as part of the complete branch method under one aggregate budget.

## Scope

1. Create versioned manifests and an execution helper that materialize the
   parent fixtures and all four child context arms from the same snapshot.
2. Ensure context-mode selection is explicit in every child command, event,
   continuation report, and analysis row.
3. For `preflight_verification`, collect preflight status, pass/fail counts,
   failing-test names (bounded), availability/error state, and duration.
4. Record prompt/token/cost and wall-clock effects per mode, including
   preflight overhead. All children use the hard child token cap from T001.
5. Produce paired analysis by parent fixture: each mode's child outcome is
   compared with its sibling modes from the same selected snapshot.
6. Update the terminal-bench task log with valid/invalid fixture counts and
   per-mode outcomes after the batch.

## Out of Scope

- Changing snapshot selection, stage-aware branching, archive scoring, or the
  root/child budget allocation.
- Creating a combined `critical_parent_summary + preflight_verification` mode.
  Consider it only after this study establishes whether each component helps.
- Treating a context-mode winner as the headline branching result without the
  T002 matched clean-retry experiment.
- Re-running or replacing roots selectively after viewing child results.
- Passing full transcripts, parent solution claims, or model-generated
  summaries outside the existing mode definitions.

## Implementation Guidance

- Reuse existing `context_mode` plumbing. Add only the smallest orchestration
  and analysis support needed to fan out children from one selected snapshot.
- Persist an explicit `fixture_id`/parent-run identifier and snapshot name in
  every child row. Never infer pairs from job names alone.
- Use `critical_parent_summary` exactly as implemented: it supplies skeptical
  parent trajectory context, not verifier output.
- Use `preflight_verification` exactly as implemented: it verifies the restored
  sandbox and reports CTRF-derived state, not the parent’s self-report.
- A preflight-unavailable child is still a valid execution of that mode if it
  starts and the unavailable reason is recorded. Analyze it separately from a
  child that never restores/runs.
- Retain raw outcomes. Do not collapse a child that starts from an already
  passing snapshot into a generic success without recording the preflight
  result and whether it regressed.
- Keep the context prompt input included in observed model-token accounting;
  report preflight time separately from model tokens.

## Primary Outcomes

For each mode, report:

- child solve rate across valid parent fixtures;
- paired win/loss/tie counts against `none` from the same fixture;
- restore validity and infrastructure-invalid rate;
- actual child tokens, cost, agent execution time, restore time, and preflight
  duration;
- for preflight: current verifier pass/fail counts and whether an initially
  passing restored state regressed;
- repeated setup/test/discovery work and branch-diversity fields when those
  artifacts are available.

The primary decision is not “highest raw solve rate” alone. Nominate a mode
for T002 only if it has complete artifacts, does not materially reduce paired
solve rate versus `none`, and has a credible benefit in solve rate, avoiding
regressions, or reducing repeated work relative to its added overhead. Report
uncertainty; 15 parent fixtures is an initial study, not conclusive evidence.

## Acceptance Criteria

- The five listed tasks and three root fixtures per task are pre-registered in
  a committed manifest before child outcomes are inspected.
- Every valid fixture launches all four context children from the exact same
  selected snapshot with identical non-context configuration and token cap.
- Every child result can be paired to its parent fixture, snapshot, and sibling
  modes through explicit lineage fields.
- Analysis provides per-task and pooled paired outcomes, with invalid fixtures
  and preflight-unavailable results reported separately.
- Reports distinguish snapshot-only, resume-notice, critical-summary, and
  preflight-verification behavior; no mode is mislabeled as another.
- The result memo states only a context-mode selection conclusion and clearly
  defers the clean-retry headline claim to T002.

## Test Coverage

- Unit-test plan generation to ensure all four child plans use one snapshot,
  one fixture ID, equal child caps, and only differ in `context_mode`.
- Test that no child is planned when the fixture lacks an archive, selected
  snapshot, or verified restore reference; assert the same invalid reason is
  recorded for all modes.
- Test context-mode serialization through manifests, continuation plans,
  events, reports, and analysis rows.
- Regression-test `preflight_verification` CTRF parsing and its unavailable
  fallback; ensure it does not silently become `none`.
- Unit-test paired analysis with synthetic four-mode fixture outcomes,
  including missing/invalid sibling results and an initially passing snapshot
  that a child regresses.
- Keep existing `critical_parent_summary` prompt-contract tests intact.

## Validation

Run:

```bash
uv run pytest \
  tests/test_preflight.py \
  tests/test_snapshot_agent.py \
  tests/test_continuations.py \
  tests/test_experiment_runner.py \
  tests/test_analysis_tables.py \
  tests/test_cli.py -q
uv run pytest -q
```

Before the live batch, dry-run one fixture and inspect all four generated child
commands. Confirm they reference the same Daytona snapshot and differ only in
the explicit context-mode agent kwarg and job name.

## Notes / Open Questions

- If the fixed-parent study selects `preflight_verification` and
  `critical_parent_summary` each show independent value, create a separate
  implementation and ablation ticket for their combined mode. Do not assume
  their effects add.
- The parent fixture cost is deliberately shared in this study. T002 must
  later charge root and child costs as one complete branch arm.
