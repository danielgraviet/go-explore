# T009 — Implement diff + command log

## Goal

Add the `diff_only + command_log` condition from `docs/essay.md` as a real
experiment arm. The child should receive:

- a clean repo,
- the parent git diff,
- the parent command log with observed results.

This is the most explicit compressed-memory baseline short of full replay.
It tests whether giving the child the exact setup/discovery sequence is enough
to recover the missing sandbox state.

## Problem

We already have the building blocks for the diff side:

- `clean` starts,
- `diff_only` filesystem application,
- `full_snapshot` continuations,
- parent trajectory data in `jobs/<root>/<trial>/agent/trajectory.json`,
- ATIF parsing helpers and signal extraction.

What is missing is a deterministic way to convert the parent trajectory into
an execution log artifact that preserves commands and observed outputs without
turning this into a full replay system.

Do **not** implement command replay here. This ticket is about text memory,
not executing the history again.

## Implementation Plan

### 1. Reuse the existing diff path

Keep the current `diff_only` filesystem behavior from T007:

- clean environment,
- apply the parent `git diff`,
- fail fast with `DiffApplyFailed` if the patch does not apply.

Do not duplicate diff application logic.

### 2. Build a deterministic command-log extractor

Create a helper that reads `trajectory.json` and emits a compact command log
artifact for the child.

Use the existing trajectory utilities rather than raw JSON scraping:

- `load_atif_trajectory_steps`
- `extract_signals_from_atif_step`
- `process_atif_trajectory` if it already exposes the command/output structure

The artifact should preserve the shape of the run, not a prose summary. At
minimum, include:

- ordered commands,
- terminal outputs or the shortest useful excerpt,
- exit status or pass/fail counts when available,
- file edits and test runs,
- environment setup steps,
- final parent outcome.

Keep the log bounded so it remains a compressed condition, not a transcript
dump.

### 3. Wire the command log into `diff_only`

Extend the child-start planning path so `diff_only` can carry:

- `parent_job_dir`,
- `parent_trial_name`,
- `parent_artifacts` entries for both the diff and command-log artifacts,
- a `context_mode` that receives the command log text.

The child still starts from the diff-applied clean repo. The command log is
only memory transfer.

### 4. Keep it deterministic

The command log should be generated from local artifacts only. Avoid any
model-generated compression or hand-authored narration.

The point of this arm is to test whether more exact execution memory helps
relative to summary memory and relative to full snapshots.

### 5. Add a small pilot

Run the arm on a narrow set first:

- `regex-log`
- `build-cython-ext`
- `git-leak-recovery`

Compare:

- `clean`,
- `diff_only`,
- `diff_only + transcript`,
- `diff_only + command_log`,
- `full_snapshot`.

## Deliverables

- Command-log extraction helper.
- `diff_only + command_log` planning/execution path.
- Unit tests for command-log generation and artifact wiring.
- Narrow pilot run with analysis tables.
- Short memo on whether exact command memory beats summary memory.

## Acceptance Criteria

- Command-log generation is deterministic and does not require a model call.
- The artifact records commands and outputs in a bounded, inspectable form.
- `diff_only + command_log` can be planned and executed from the same parent
  root as `diff_only` and `diff_only + transcript`.
- The child prompt receives both the applied diff and the command-log artifact.
- The pilot can compare command-log memory directly against transcript memory
  and full snapshots.

## Validation

Before any larger batch:

- inspect one generated command-log artifact directly,
- confirm it reflects the parent trajectory rather than a replay manifest,
- confirm `diff_only` still fails cleanly when the diff does not apply,
- run a narrow pilot and build the analysis tables.

## Out Of Scope

- `command_replay`
- executor-level replay of shell history
- model-generated summaries
- changes to the snapshot selector
- changes to the root branch policy

## Status

Planned. This ticket should follow the `diff_only` plumbing already laid down
for T007 and reuse the same diff application path.
