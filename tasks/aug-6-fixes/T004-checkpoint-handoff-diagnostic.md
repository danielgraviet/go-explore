# T004: Diagnose Snapshot Value Versus New-Agent Handoff Cost

## Goal

Implement a small, auditable checkpoint diagnostic that separates three
questions currently conflated by root-then-child experiments:

1. Was the root checkpoint a genuinely useful development state?
2. Can a new agent exploit that state after Daytona restore?
3. Is a clean restart stronger than either continuation?

From the same recorded root checkpoint, compare an original root continuing
with its existing agent context, a new child restored from the full snapshot,
and a new clean agent starting from the original task. Give every post-
checkpoint attempt the same model, task settings, and remaining token cap.

## Context

The existing branch benchmark combines checkpoint quality, snapshot fidelity,
new-agent orientation, and alternative reasoning into one final outcome. When
a child fails, it is unclear whether the selected state was misleading or
whether the state was useful but the child paid too much to reconstruct the
parent's situation.

The original root has information a restored child does not: its active
conversation/context and direct knowledge of why it took prior actions. This
is not an unfair nuisance in this diagnostic—it is the quantity being
measured, the **handoff tax** of a full-sandbox snapshot without the original
agent's working memory.

This is a mechanism study. It is not a replacement for a matched,
fixed-total-budget branch-versus-retry benchmark and must not be reported as
one.

Relevant references:

- `docs/headline-blockers.md` (budget exhaustion and child reorientation)
- `docs/experiments/t002-exp2-headline-results-memo.md`
- `docs/continuation-context-modes.md`
- `go_explore/agents/snapshot_agent.py`
- `go_explore/agents/token_budget.py`
- `go_explore/continuations.py`
- `go_explore/experiment_runner.py`
- `tasks/aug-6-fixes/T001-grounded-preflight-selector.md`
- `tasks/aug-6-fixes/T002-factual-checkpoint-card.md`

## Experiment Design

For each selected root checkpoint, record a common root prefix and then
observe or execute three post-checkpoint arms:

```text
root reaches checkpoint C
          │
          ├── A. Root continuation: same live agent continues from C
          ├── B. Restored child: new agent starts from Daytona snapshot C
          └── C. Clean retry: new agent starts from original task state
```

All arms must use the same model, task timeout, verifier settings, and
post-checkpoint token cap `R`.

- **A** retains both the root's live sandbox and its agent/context history.
- **B** receives the full saved sandbox and the configured factual/preflight
  continuation context, but no parent reasoning transcript.
- **C** receives the original task and a clean sandbox, with no root state.

The root-prefix cost is shared diagnostic setup, not hidden from accounting.
The report must show it separately from every arm's post-checkpoint cost.

## Scope

1. Add a declarative diagnostic plan/config with:
   - task name, model, seed/repetition, root-prefix cap `P`, remaining cap `R`;
   - checkpoint selection mode and exact selected snapshot/checkpoint;
   - restored-child context mode;
   - clean-retry configuration;
   - explicit schema/version and a `diagnostic_only` marker.
2. Capture sufficient root checkpoint metadata to calculate post-checkpoint
   root continuation behavior:
   - snapshot step/id and timestamp;
   - root token usage and elapsed time at checkpoint;
   - root final result and token/time usage after checkpoint;
   - official verifier state at checkpoint when available;
   - snapshot/restore lineage and checkpoint-selection reasons.
3. Implement or document the narrowest reliable way to enforce a comparable
   remaining cap `R` for all three arms. The implementation must not pretend a
   full-root token total is post-checkpoint usage.
4. Launch/record a restored-child arm from the exact snapshot and a clean arm
   from the original task, both capped at `R` and using the same agent model.
5. Produce a versioned diagnostic report with one row per checkpoint and a
   compact human-readable interpretation field based only on observed outcomes:
   - `root_only_progress`: A succeeds/improves; B and C do not;
   - `snapshot_transfer_value`: B succeeds/improves; C does not;
   - `state_value_without_transfer_gap`: A and B succeed/improve; C does not;
   - `restart_preferred`: C succeeds/improves while A and B do not;
   - `inconclusive`: insufficient artifacts, infra failure, or no clear split.
6. Include outcome, canonical-verifier result when available, token use,
   elapsed time, snapshot/restore/preflight overhead, repeated-work metrics,
   and all unavailable-data reasons for each arm.
7. Add a small runbook section and a result-memo template that label this
   experiment as a diagnostic rather than an aggregate solve-rate claim.

## Out of Scope

- Replacing the existing headline benchmark or retroactively reanalyzing it as
  this diagnostic.
- Claiming equal aggregate compute across methods. The root prefix plus three
  post-checkpoint arms intentionally costs more than a single branch chain.
- Dynamic early branching, online child launch, multi-depth search, or budget
  reallocation policy.
- Transferring the parent's transcript/reasoning to the child. Use only the
  configured factual/preflight child context.
- Learned selection or task-specific success interpretation.
- Making a child failure count as a snapshot restore failure unless lineage or
  environment evidence actually shows restore failed.

## Implementation Guidance

### First resolve feasibility, then automate

The critical technical question is whether the wrapped root agent exposes a
reliable checkpoint token/time boundary while it continues with its original
in-memory context. Do a short implementation spike first and write down the
result:

- If the wrapper can capture a checkpoint counter and continue normally, use
  that path; compute A's post-checkpoint usage as final minus checkpoint usage.
- If the root cannot be stopped/resumed at an exact cap without losing context,
  do not fabricate an “original root continuation” arm. Implement a bounded
  observation-only A arm and mark `R` comparability as unavailable, or stop
  and return a documented blocked conclusion before launching a paid batch.

Keep root/child execution logic separate from pure report classification.
Classification must operate on typed observed arm records and preserve
ambiguous cases rather than selecting a flattering label.

### Make improvement measurable

For v1, use a simple ordered outcome for “improves”:

1. task verifier reward/success;
2. official verifier pass fraction, when comparable counts exist;
3. otherwise no improvement claim.

Do not infer improvement from agent prose, a successful shell command, or an
unverified file edit. Count-less verifier exit results are outcomes but not
partial-progress comparisons.

### Keep accounting explicit

Report at minimum:

```text
root prefix: tokens/time through C
root continuation: incremental tokens/time after C
restored child: tokens/time plus restore and child-preflight overhead
clean retry: tokens/time from clean start
```

The clean retry has no root prefix associated with its own attempt. The report
must say whether readers should compare post-checkpoint effort only or total
diagnostic spend; never collapse the two silently.

## Acceptance Criteria

- The plan/report labels every run `diagnostic_only` and prevents accidental
  inclusion in fixed-budget headline aggregation.
- Every three-arm family has explicit lineage from A/B to the same checkpoint
  and explicit clean-start provenance for C; job-name inference alone is not
  sufficient.
- Root post-checkpoint token/time fields are measured as deltas from the
  checkpoint, or explicitly marked unavailable with the documented reason.
- B restores the exact selected Daytona snapshot and retains normal
  restore-lineage verification and child preflight behavior.
- B and C use the same model/task settings and remaining token cap `R`.
- The report includes root-prefix costs separately and never describes the
  diagnostic as an equal-total-budget solve-rate comparison.
- Interpretation labels are deterministic and based only on verified outcomes
  and comparable official verifier data.
- Infrastructure failures, missing snapshot lineage, unavailable verifier
  results, and cap-enforcement uncertainty produce `inconclusive`, not an
  outcome favorable to any arm.
- Existing experiment-runner modes and reports continue to work unchanged.

## Test Coverage

- Unit-test plan/config validation, including invalid caps, missing checkpoint
  identifier, non-snapshot child arm, and mismatched model/task settings.
- Unit-test root post-checkpoint delta calculation, including exact counters,
  missing checkpoint counters, and counter-overrun/error cases.
- Unit-test report classification for every listed interpretation plus mixed,
  missing, and infrastructure-failure cases.
- Unit-test lineage validation: A/B share a checkpoint, C is clean, and stale
  or mismatched snapshot identifiers are rejected.
- Unit-test accounting rendering so root prefix, root continuation, child, and
  clean costs cannot be conflated.
- Add an integration-style test with fake Harbor summaries/archive entries that
  produces a complete three-arm diagnostic artifact without calling Daytona.
- Regression-test that diagnostic artifacts are excluded from normal
  fixed-budget task-summary/figure aggregation unless an explicit future
  analysis mode requests them.

## Validation

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_snapshot_agent.py \
  tests/test_continuations.py \
  tests/test_experiment_runner.py \
  tests/test_analysis_tables.py -q
.venv/bin/python -m pytest -q
```

Before any multi-task run, execute one low-cost one-seed canary. Inspect the
report manually to confirm:

- A's usage is truly measured after the checkpoint;
- B's snapshot name and child preflight match the selected checkpoint;
- C started clean;
- all three arms use the declared `R` cap; and
- root-prefix cost is visible and separate.

## Result Interpretation

The purpose is diagnosis, not a manufactured positive result:

| Observed outcome | Meaning |
| --- | --- |
| A succeeds, B/C fail | State may be useful, but new-agent handoff/context is the limiting factor. |
| A/B succeed, C fails | The saved sandbox state is useful and transfers across agents. |
| B succeeds, C fails | Direct evidence that full snapshot restore helps a new agent more than a clean restart. |
| C succeeds, A/B fail | The checkpoint/path is misleading; restart is preferable. |
| All fail | The checkpoint/task may be too hard at `R`; no mechanism conclusion. |

Run enough pre-registered repetitions before treating any pattern as stable.
