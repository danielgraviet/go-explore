# T003: Add Structured State Signals to Snapshot Selection

## Goal

Replace the current coarse snapshot-selection inputs with deterministic,
explainable signals that identify reusable sandbox state and avoid unsafe or
misleading states. The selector must distinguish setup, real validation,
persistent implementation progress, and risky mutation before ranking archive
entries.

This ticket implements the structured rule-based approach only. It does not
implement diversity-aware selection, a learned selector, or new experiment
claims.

## Context

The archive currently treats a cell largely as the set of changed files and
ranks it with event type, test counts, and a small file-edit bonus. That loses
important distinctions:

- `pip install` can produce valuable reusable setup state but is not a passed
  task test; an earlier KV run accidentally treated install output as one.
- A file edit may be meaningful implementation progress or an unsafe final
  answer/destructive cleanup.
- A read-only discovery command such as `git log` can help the parent, but a
  child using `context_mode=none` does not inherit that knowledge. It should
  not be selected merely as “progress” unless it leaves reusable sandbox state.
- Generic changed-file cells can conflate setup, speculative edits, and
  validated work.

The immediate objective is better metadata and a conservative, inspectable
heuristic. It should make later diversity selection and empirical comparison
possible without pretending that rules are a learned value function.

Relevant references:

- `docs/terminal-bench-task-log.md`
- `docs/phase6-failure-analysis.md` sections 1–4
- `go_explore/snapshots/policies.py`
- `go_explore/snapshots/models.py`
- `go_explore/snapshots/archive.py`
- `go_explore/snapshots/selectors.py`
- `tests/test_selectors.py`, `tests/test_archive.py`, and
  `tests/test_snapshot_components.py`

## Scope

1. Add a small immutable structured-signal representation for a snapshot
   candidate. It must support these independent labels:
   - `setup_complete`: reusable dependency, build, generated-artifact, or
     service-ready state;
   - `validation`: a recognized task test/verifier command and its observed
     pass/fail evidence;
   - `persistent_progress`: task-relevant file edits or generated artifacts
     that remain in the restored sandbox;
   - `discovery_persisted`: a discovery action that creates a reusable
     artifact/state, not a read-only observation alone;
   - `risk`: final-answer-file edits, destructive cleanup/mutation, or an
     unvalidated bulk edit.
2. Derive these labels using deterministic command and observation rules in a
   focused helper/module. Preserve the raw command, event, changed files, and
   existing probe metadata for auditability.
3. Require validation labels to come from recognized test/verifier or explicit
   assertion probes. Generic command success, including package-install output,
   must never create a validation-pass signal.
4. Update the archive entry schema and persistence so selected states retain
   their structured signals and human-readable reasons. Existing archives must
   remain readable with safe defaults for absent fields.
5. Add a selector mode or replace the current default only after preserving a
   named legacy baseline. The structured selector must:
   - reject states with disqualifying `risk` unless they also have explicit
     positive validation evidence;
   - rank validated progress highest;
   - rank confirmed reusable setup and persistent implementation progress next;
   - give no positive selection bonus to read-only discovery under
     `context_mode=none`;
   - emit every feature and score contribution as selector reasons.
6. Record the selector mode, structured signals, and reasons in archive,
   selection events, and continuation reports so later experiments can audit
   why a snapshot was chosen.

## Out of Scope

- Selecting a diverse set of cells across stages/files/categories (follow-up
  work).
- Learned, LLM, oracle, or outcome-trained selectors.
- Changing token budgets, continuation context, snapshot timing, or snapshot
  backend behavior.
- Automatically writing a parent’s read-only discoveries into context or task
  files. Parent knowledge transfer is a separate context-mode question.
- Proving a solve-rate improvement; this ticket supplies a selector suitable
  for testing in T002.

## Implementation Guidance

- Prefer a frozen dataclass (for example, `SnapshotStateSignals`) over a loose
  metadata dictionary. Keep detection pure and independently unit-testable.
- Treat the labels as multi-label facts, not a replacement for
  `SnapshotEvent`. A successful build can be both `setup_complete` and
  `persistent_progress`; a file edit can be both progress and risk.
- Define a narrow initial allowlist for setup and validation detection. False
  validation positives are more harmful than missed candidates.
- Define final-answer/destructive patterns conservatively and preserve the
  exact matching reason. Examples include task-designated answer files,
  irreversible Git cleanup, database truncation, and bulk replacement commands
  without a subsequent validation signal.
- Do not infer persistence from a read-only command. `git log`, `git reflog`,
  `grep`, `cat`, and similar inspection commands are parent-only knowledge
  unless the command writes a durable artifact that the child can use.
- Score components should be named constants or small helpers, not unexplained
  numeric literals in a long conditional. Keep the scoring policy compact and
  documented beside the selector.
- Maintain backwards compatibility for `archive.json`. Missing signal fields
  must deserialize to neutral/unknown values; historical entries must not gain
  fabricated evidence.

## Suggested Starting Points

- Trace candidate creation through `InterestingAgentStepPolicy` and
  `_probe_signal` in `go_explore/snapshots/policies.py`.
- Inspect `SnapshotCandidate`/`SnapshotEvent` in
  `go_explore/snapshots/models.py` and archive serialization in
  `go_explore/snapshots/archive.py`.
- Preserve the existing `archive_priority`, `validated_progress`, and
  `partial_progress` modes in `go_explore/snapshots/selectors.py` as
  comparison baselines.
- Use the historical `kv-store-grpc`, `git-leak-recovery`, `regex-log`,
  `sqlite-db-truncate`, and `sanitize-git-repo` trajectories as fixture cases.

## Acceptance Criteria

- Each newly created candidate/entry records structured labels and explicit
  detection reasons for setup, validation, persistent progress,
  persisted discovery, and risk where applicable.
- Package-install success is classified as setup when appropriate and never as
  a passing test solely because its output says “success” or “installed.”
- A recognized test/verifier result records its actual pass/fail evidence and
  is distinguishable from setup success.
- Read-only discovery receives no positive score in the structured selector
  for snapshot-only (`context_mode=none`) continuation.
- Risky final-answer/destructive/unvalidated-bulk states are ineligible unless
  the policy's documented validation exception applies; selector reasons make
  the decision auditable.
- The structured selector produces deterministic ordering and records every
  score contribution/rejection reason.
- Legacy archives load successfully and legacy selector modes preserve their
  current behavior.
- Selection events and continuation reports contain the new selector mode,
  signals, and reasons.
- `uv run pytest -q` passes.

## Test Coverage

- Unit-test pure signal extraction for:
  - dependency install/build/service-ready commands;
  - `pytest`/recognized verifier pass, fail, and mixed output;
  - generic “Successfully installed” output (must not be validation);
  - generated stubs and task-relevant file edits;
  - read-only Git/database/log discovery (not persistent progress);
  - persistent discovery artifacts, if supported;
  - final-answer, destructive, and bulk-edit risk patterns.
- Unit-test selector ordering and rejection with a compact table of synthetic
  archive entries: validated progress, setup-only, safe edit, read-only
  discovery, and risky unvalidated edit.
- Regression-test the historical KV false-positive shape and the
  `git-leak-recovery` discovery shape.
- Test archive JSON round trips for new signals and loading an old archive with
  no signal fields.
- Test selection-event and continuation-report serialization for reasons and
  signals.

## Validation

Run:

```bash
uv run pytest \
  tests/test_selectors.py \
  tests/test_archive.py \
  tests/test_snapshot_components.py \
  tests/test_continuations.py -q
uv run pytest -q
```

Before requesting review, replay at least one saved positive setup trajectory
and one saved negative/risky trajectory through the policy offline. Inspect the
resulting archive/selection JSON and confirm the selected reasons match the
actual command and verifier evidence.

## Notes / Open Questions

- Task-specific final-answer files may be unavailable from generic Harbor
  metadata. Start with conservative command/path heuristics and record when a
  risk determination is unknown rather than overclaiming safety.
- A service may be “started” but not healthy. Award `setup_complete` only for
  observable readiness evidence, not merely a launch command.
- Diversity-aware selection should consume these structured labels in a later
  ticket; do not fold that policy into this change.
