# T001: Rank Snapshot Checkpoints by Official Verifier Progress

## Goal

Add a conservative `grounded_partial_progress` snapshot selector that uses the
same Terminal-Bench verifier already run for `preflight_verification` child
handoff to decide *which root checkpoints are worth branching from*.

For a bounded set of meaningful root checkpoints, run the task's official
verifier before creating the snapshot, persist the observed result with the
archive entry, and select children from verified partial progress rather than
from heuristic file-edit/discovery scores alone.

The result must be auditable: an experiment report should say exactly which
official verifier result caused each snapshot to be selected or rejected.

## Context

The current `preflight_verification` context mode is valuable and should be
preserved. It restores an already-selected snapshot, runs `/tests/test.sh`,
reads CTRF counts when available, and gives the child the actual pass/fail
state plus failing-test names. See:

- `go_explore/snapshots/preflight.py`
- `go_explore/agents/snapshot_agent.py`

However, this happens *after* snapshot selection. The experiment runner first
chooses archive entries using `archive_priority`, then starts restored children.
The archive's present test metadata comes from command/observation heuristics
in `InterestingAgentStepPolicy`; it is not proof that the official
Terminal-Bench verifier was run on that exact saved state. This permits weak
states—unvalidated edits, scratch-test results, or discovery snapshots—to
outrank a checkpoint with real partial progress.

The completed headline experiment used `preflight_verification` but still
used `archive_priority` to select children. Retry beat promising branching
17/25 to 6/25, while a few roots were rescued by children. The next selector
experiment should therefore test a different selection policy without changing
or rewriting that already-reported result.

Related work:

- `docs/experiments/t002-exp2-headline-results-memo.md`
- `docs/headline-blockers.md`
- `tasks/phase-7-fixes/T003-improve-state-selection.md`
- `tasks/phase-7-fixes/T004-stage-aware-branching.md`
- `tasks/phase-7-fixes/T006-evaluate-continuation-context-modes.md`
- `go_explore/snapshots/policies.py`
- `go_explore/snapshots/archive.py`
- `go_explore/snapshots/selectors.py`
- `go_explore/experiment_runner.py`

## Definitions

- **Agent-observed validation:** a test-like command and output inferred from
  the agent trajectory. This remains useful telemetry, but is not ground
  truth.
- **Grounded verification:** `run_preflight_verification()` ran the task's
  own verifier against the exact sandbox checkpoint. Its CTRF counts and
  failing-test names, when available, are ground truth for this feature.
- **Grounded partial progress:** a grounded verification result with a
  measurable incomplete state: verifier status `failed`, count data available,
  and at least one passing test. It is deliberately not a fully passing task.
- **Checkpoint:** a candidate root state that has passed the cheap structural
  filter and is eligible to spend one bounded official-verifier probe.

## Scope

1. Introduce a typed, versioned `GroundedVerification` value associated with a
   snapshot candidate/archive entry. It must include:
   - status: `passed`, `failed`, or `unavailable`;
   - `tests_passed`, `tests_failed`, and `tests_total` when CTRF provides them;
   - bounded failing-test names or a stable fingerprint/hash of them;
   - verifier command, timeout, observed duration, and unavailable/error
     reason when applicable;
   - root checkpoint order/step id and a clear provenance marker such as
     `source="official_preflight"`.
2. Add a bounded checkpoint-probe path during the root run:
   - use existing candidate/state-signal logic as a cheap structural filter;
   - probe only meaningful candidates, initially validation-adjacent,
     verified-setup, or persistent-progress candidates;
   - do not run the verifier after every agent command;
   - expose a conservative per-root limit (default proposed: 3) and a timeout
     (default proposed: the existing 180 seconds);
   - run the official verifier **before** taking the snapshot, so the saved
     state is the state whose result is recorded;
   - never fail or stop the root agent when a probe is unavailable, times out,
     or errors.
3. Persist grounded verification in `archive.json`, snapshot-created events,
   snapshot-selected events, continuation reports, and normalized analysis
   rows. Old archives without the new field must still load unchanged.
4. Add `grounded_partial_progress` as an explicit selector mode. It must:
   - consider only entries with grounded verifier count data and `failed`
     status;
   - require at least one passing test by default;
   - reject entries with no grounded result, unavailable results, and fully
     passing results, recording why;
   - rank eligible entries by higher official pass fraction, then fewer
     official failures, then deterministic existing archive tie-breakers;
   - prefer a checkpoint that improved over the earliest grounded root
     baseline when comparable counts exist; record the baseline and delta;
   - avoid selecting duplicate archive cells/stages when the underlying
     archive metadata supports that distinction;
   - return fewer than `k` entries when evidence is insufficient, rather than
     silently falling back to ungrounded `archive_priority` entries.
5. Keep the child-side `preflight_verification` behavior unchanged. A selected
   child must still independently re-run preflight after restoration; this is
   a restore-integrity check, not redundant selection metadata.
6. Thread the new selector through CLI, continuation planning, fixed-budget
   manifests, experiment runner configuration, event/report schemas, and
   analysis table serialization. Existing selector defaults must not change.
7. Write a short runbook section or experiment note explaining how to run the
   new selector, its probe budget, and how probe time is accounted for.

## Out of Scope

- Replacing `preflight_verification` child context or changing its prompt.
- Changing the historical Experiment 2 result, its task set, or its headline
  numbers.
- Learned/LLM/oracle selection, task-specific rules, or semantic analysis of
  failing tests.
- Arbitrary testing of every saved snapshot or an unbounded number of Daytona
  restores solely to rank snapshots.
- Early root interruption, concurrent child launch, adaptive budget
  reallocation, or fallback-to-retry execution policy. If no grounded entries
  are selected, this ticket records that outcome; a fair use of unspent child
  budget is a separate experiment-design ticket.
- Treating a verifier result as a proof of persistent setup value. Setup is a
  tie-break/eligibility signal, while verifier progress is the evidence basis.

## Design Constraints

### Preserve the exact-state invariant

The archive must not claim that a verifier result describes a snapshot if the
result was obtained from some later or different state. For v1, execute the
preflight verifier on the live root environment immediately before snapshot
creation, then snapshot that resulting environment. Record that the verifier
itself may leave normal verifier artifacts in the saved state.

If the live-root interface cannot safely support this ordering, do not fake
the association. Instead, implement a bounded restore-and-probe path and
record its extra sandbox cost explicitly; decide between the two designs with
a small test before broad execution.

### Treat verifier unavailability as unknown

Preflight has explicit unavailable cases: unsupported environment, missing
test directory, upload/exec error, timeout, or unparseable output. None may
be converted to pass/fail or given a heuristic score. Preserve the reason in
the archive and report it in analysis.

### Do not select solved states as partial-progress branches

A fully passing grounded state should be recorded accurately but excluded from
this selector's continuation candidates. The existing runner's policy for a
root that already solved is separate. This prevents spending a child slot on
a state that should instead end the task.

### Keep budget accounting honest

Grounded probes consume Daytona wall-clock time and may consume sandbox cost,
but not model tokens. Persist their count, duration, and failures separately
from child preflight time and snapshot-creation time. Do not claim an equal
end-to-end budget comparison unless the experiment includes that overhead in
both arms or reports it separately.

## Suggested Implementation Plan

1. Read the existing preflight result type and extract a reusable immutable
   representation suitable for archive persistence. Avoid importing agent
   code into pure archive/selector modules.
2. Add archive/model schema fields with backward-compatible JSON loading.
   Define serialization once; do not store these fields only in an untyped
   metadata dictionary.
3. Add a small root-side probe coordinator near snapshot capture. It should
   receive an already-filtered candidate, enforce the per-root cap, invoke the
   existing preflight helper, attach the result, and only then ask the Daytona
   backend to snapshot.
4. Add pure selector functions and reason strings. Ranking must be deterministic
   and unit-testable from synthetic archive entries—no Daytona dependency.
5. Thread mode/config/report fields through the existing paths, preserving all
   older modes byte-for-byte where practical.
6. Add tests before a live run. Then run a cheap one-seed canary and inspect
   raw archive/event/report artifacts before launching a comparison pilot.

## Acceptance Criteria

- A newly created grounded archive entry contains an official verifier result
  with provenance, checkpoint id, counts when available, and probe timing.
- The verifier is invoked at most the configured cap per root, only for
  structurally eligible checkpoints; ordinary agent steps do not trigger it.
- Snapshot creation follows the verified checkpoint so the persisted result
  refers to the saved state. The implementation documents and tests this
  ordering.
- `grounded_partial_progress` never selects a file-edit/discovery entry merely
  because its legacy heuristic score is high.
- With synthetic grounded entries, selection prefers a state with 8/10 tests
  passing over 4/10, then a state with fewer failures when pass fractions tie;
  ties are deterministic and explained.
- Entries with status `unavailable`, count-less exit-code-only results, zero
  passed tests, and fully passing results are excluded by default and produce
  auditable rejection reasons.
- When no eligible grounded entries exist, the selector returns no entries;
  the run report clearly shows `skipped_no_grounded_candidate` (or an
  equivalently precise status), not a disguised fallback.
- A selected child still runs its independent child-side preflight and the
  report distinguishes `selection_preflight_*` from `child_preflight_*`.
- Legacy archives and all existing selector modes load and behave as before.
- Manifests, events, continuation reports, and analysis outputs include mode,
  probe counts/durations, grounded result fields, baseline/delta, and selector
  reasons where applicable.
- The focused test suite and full unit suite pass.

## Test Coverage

- Unit-test grounded verification serialization/deserialization, including
  complete counts, exit-code-only, unavailable, bounded failing-test data, and
  legacy entries with no grounded fields.
- Unit-test the root probe coordinator with fake environment/backend objects:
  cap enforcement, structural filter, success, unavailable result, timeout,
  and exact verifier-before-snapshot call order.
- Unit-test selector eligibility and ordering for improved, unchanged, worse,
  zero-pass, fully passing, unavailable, and count-less entries. Verify all
  reason strings and deterministic ties.
- Test baseline comparison when a root has several checkpoints with compatible
  test totals, and test a safe unknown result when totals differ or no baseline
  exists.
- Regression-test that generic package-install success, file edits, scratch
  tests, and read-only discovery cannot become grounded progress without an
  official preflight result.
- Test CLI/config/manifest round trips and continuation/event/report/analysis
  joins for the new mode. Confirm no regression for `archive_priority`,
  `validated_progress`, `partial_progress`, `random`, and explicit selection.
- Add a focused snapshot-agent integration test confirming the selected child's
  preflight still runs after restore even when its parent had a grounded
  result.

## Validation

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_snapshot_components.py \
  tests/test_archive.py \
  tests/test_selectors.py \
  tests/test_snapshot_agent.py \
  tests/test_continuations.py \
  tests/test_experiment_runner.py \
  tests/test_analysis_tables.py -q
.venv/bin/python -m pytest -q
```

Before review, run one cheap live canary with the new mode and inspect:

- root `archive.json` for checkpoint-level grounded results;
- `events.jsonl` for probe and selection provenance;
- continuation report for selection reasons and independent child preflight;
- analysis CSV for separate probe, snapshot, restore, and child-preflight
  overhead.

Do not launch a multi-task paid comparison until the canary confirms that the
recorded verifier result and restored child preflight describe the same state
or any mismatch is explicitly classified.

## Follow-up Experiment (Separate Ticket)

After this implementation is validated, compare `grounded_partial_progress`
against `archive_priority` under the same root/child split and the same
`preflight_verification` child context on 2–3 pre-registered tasks. Report:

- branch solve rate and paired root-failure recoveries;
- selected checkpoint pass/fail distributions and improvement over baseline;
- fraction of roots with no grounded eligible checkpoint;
- probe, snapshot, restore, and child-preflight overhead separately;
- repeated setup/discovery work where event traces support it.

This follow-up tests whether grounded selection improves branching; it must
not be merged into the completed Experiment 2 headline result.
