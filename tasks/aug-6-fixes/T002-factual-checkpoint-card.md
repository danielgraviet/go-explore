# T002: Add a Factual Checkpoint Card for Restored Children

## Goal

Give each snapshot-restored child a short, machine-generated checkpoint card
that removes avoidable environment and verification rediscovery without
transferring the parent agent's reasoning.

The card supplements the existing `preflight_verification` context mode. It
must present only observable facts about the restored checkpoint and explicitly
state that inherited edits are untrusted until the canonical verifier passes.

## Context

`preflight_verification` already runs the task's official `/tests/test.sh`
after restore and tells the child the current pass/fail result, failing tests
when CTRF is available, and the command to rerun. Do not duplicate or replace
that mechanism.

Children nevertheless can spend turns rediscovering their workspace, which
files the prior attempt changed, and whether setup or generated artifacts are
already present. A long parent summary is not the answer: it can anchor the
child to a failed approach. The desired handoff is a compact facts-only card.

Relevant files:

- `go_explore/agents/snapshot_agent.py`
- `go_explore/snapshots/preflight.py`
- `go_explore/continuations.py`
- `go_explore/snapshots/models.py`
- `go_explore/snapshots/archive.py`
- `docs/headline-blockers.md`
- `docs/continuation-context-modes.md`

## Scope

1. Add an opt-in continuation context mode named `factual_checkpoint_card`.
   It must retain the existing child-side preflight verification behavior.
2. Generate a bounded card from deterministic snapshot/archive/preflight
   facts, using no model call and no free-form summary of the parent trajectory.
3. Include, when available:
   - task workspace / current working directory;
   - canonical verifier command (`/tests/test.sh`);
   - the restored child's current preflight result: pass/fail counts and a
     bounded list of failing tests;
   - changed files recorded for the selected snapshot;
   - verified setup/persistent-state facts already recorded in archive metadata
     or structured signals (for example, generated artifact or service-ready
     facts). Do not invent package/service state by parsing a parent summary;
   - snapshot identifier and checkpoint step for auditability.
4. Append a concise trust rule:

   > The sandbox contains work from a prior attempt. Treat inherited edits as
   > hypotheses, not proof. Do not declare the task complete until the canonical
   > verifier passes.

5. Persist the rendered card (or its stable hash and structured source fields)
   beside the continuation artifacts so experiment analysis can confirm what
   the child received.
6. Thread the mode through CLI choices, continuation plans/reports, manifest
   serialization, and analysis rows without changing any existing mode's
   output or default behavior.

## Out of Scope

- Changing snapshot selection or the `grounded_partial_progress` ticket.
- Replacing the official child-side preflight verifier.
- Sending a parent transcript, parent model reasoning, inferred root cause, or
  recommendation for a particular fix.
- Running new sandbox probes merely to fill in the card.
- Changing token budgets, root/child allocation, or branching timing.
- Claiming that the card improves solve rate without a separately registered
  comparison experiment.

## Implementation Guidance

- Build the card through a pure formatter over a small typed facts object.
  Keep archive loading and live preflight side effects outside that formatter.
- Prefer absence to guessing. Omit unavailable fields or label them
  `unavailable`; never turn a generic successful command into evidence that a
  dependency is installed or a service is healthy.
- The preflight result must describe the restored child sandbox, not a stale
  root result. If parent checkpoint verification from T001 exists, it may be
  shown only as separately labelled historical checkpoint evidence.
- Bound all variable-length content: at most 10 failing-test names, a bounded
  number of changed files, and no raw command/output transcript.
- Keep the card clearly separated from the user task instruction, as the
  current preflight augmentation does.
- Reuse existing context-mode plumbing and the `preflight_verification`
  formatter where practical. Avoid a second verifier implementation.

## Example Child Context

```text
Restored checkpoint facts:
- Workspace: /app
- Snapshot: go-explore-task__abc-step-8
- Canonical verifier: /tests/test.sh
- Current verifier result: 7 of 10 tests passed.
- Failing: test_parse_dates, test_timezone_edge_case, test_empty_input
- Snapshot changed files: /app/parser.py, /app/config.py
- Persisted state: generated protobuf files present

The sandbox contains work from a prior attempt. Treat inherited edits as
hypotheses, not proof. Do not declare the task complete until the canonical
verifier passes.
```

## Acceptance Criteria

- `factual_checkpoint_card` is available only for snapshot-restored
  continuations and still runs child-side preflight verification.
- The child receives the canonical verifier command and the preflight result
  for its own restored sandbox, not a parent self-report.
- The card includes only deterministic facts from archive/snapshot/preflight
  data and contains no parent transcript or inferred fix advice.
- Missing metadata is represented as omitted/unavailable rather than guessed.
- Content bounds prevent large changed-file lists, failing-test lists, raw test
  output, or trajectories from entering the prompt.
- The selected continuation's artifact/report records the card's structured
  source data or a stable hash plus the rendered card path.
- Existing context modes, especially `none` and `preflight_verification`, keep
  their current behavior.
- Focused tests and the full unit suite pass.

## Test Coverage

- Unit-test pure card formatting with complete facts, partial facts, and all
  unavailable fields; assert bounds and trust language.
- Test that preflight counts/failing tests in the card come from the restored
  child environment.
- Test that changed files and setup facts are rendered when present and omitted
  when absent.
- Test that a parent trajectory string or free-form summary cannot enter the
  card through the formatter API.
- Test context-mode CLI/config/manifest/report serialization and legacy-mode
  compatibility.
- Add a snapshot-agent integration test verifying card generation occurs after
  child preflight and before the wrapped agent receives its instruction.

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

Before review, use a fake restored environment with known CTRF results and an
archive entry with changed files. Inspect the rendered card and continuation
report to verify that every statement is factual, bounded, and clearly tied to
the child snapshot.

## Follow-up Experiment

Run a small, separately labelled ablation with equal budget and selector:

1. `preflight_verification` (current baseline);
2. `factual_checkpoint_card` (preflight plus card);
3. optional existing fuller parent-summary mode as a diagnostic.

Report solve outcomes, tokens to the first post-restore meaningful edit,
canonical-verifier use, and repeated discovery/setup commands. Do not merge
this result into the completed Experiment 2 headline comparison.
