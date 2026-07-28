# T008 — Implement diff + transcript

## Goal

Add the `diff_only + full_transcript_summary` condition from
`docs/essay.md` as a real experiment arm. The child should receive:

- a clean repo,
- the parent git diff,
- a compact text summary of the parent trajectory.

This is the compressed-memory comparator for Claim 1. It tests whether text
memory on top of code state can approach full-snapshot performance without
restoring the whole sandbox.

## Problem

We already have:

- `clean` child starts,
- `diff_only` filesystem application,
- `full_snapshot` continuation,
- parent trajectory data in `jobs/<root>/<trial>/agent/trajectory.json`,
- ATIF parsing and signal extraction helpers.

What is missing is a cheap, deterministic way to turn the parent trajectory
into the text memory that will accompany a `diff_only` child.

Do **not** build this as a model-generated summary. That would add cost,
variance, and a second model choice to a comparison that is supposed to
isolate representation quality.

## Implementation Plan

### 1. Reuse the existing diff path

Keep the current `diff_only` filesystem behavior from T007:

- clean environment,
- apply the parent `git diff`,
- fail fast with `DiffApplyFailed` if the patch does not apply.

Do not duplicate diff application logic. This ticket should only add the
text-memory sidecar.

### 2. Build a deterministic transcript compressor

Create a small helper that reads the parent `trajectory.json` and writes a
compact transcript artifact for the child.

Use existing trajectory utilities instead of inventing a new parser:

- `load_atif_trajectory_steps`
- `extract_signals_from_atif_step`
- `process_atif_trajectory` if it already captures the useful structure

The summary should be rule-based and bounded, for example:

- task name and trial id,
- ordered list of important commands,
- file edits that matter,
- test runs and pass/fail counts,
- last verifier/test observation,
- notable dependency installs or service setup,
- whether the parent solved, failed, or timed out.

Keep it short enough to fit in the prompt without swallowing the model budget.
Prefer a structured markdown note over a prose essay.

### 3. Wire the transcript artifact into `diff_only`

Extend the child-start planning path so `diff_only` can carry:

- `parent_job_dir`,
- `parent_trial_name`,
- `parent_artifacts` entries for both the diff and transcript artifacts,
- a `context_mode` that receives the transcript text.

The child should still start from the diff-applied clean repo. The transcript
is only memory transfer.

### 4. Keep the prompt contract explicit

The transcript should not imply certainty that the parent was correct.
It should preserve the same discipline as the other context modes:

- distinguish observed test results from guesses,
- include the failure state when relevant,
- avoid “do not repeat the parent” style overreach,
- avoid model-generated reasoning.

### 5. Add a minimal pilot

Run the new arm on one or two tasks first, preferably tasks where diff state
and transcript state are both likely to matter:

- `regex-log`
- `build-cython-ext`
- `git-leak-recovery`

Compare:

- `clean`,
- `diff_only`,
- `diff_only + transcript`,
- `full_snapshot`.

## Deliverables

- Transcript-compression helper.
- `diff_only + transcript` planning/execution path.
- Unit tests for transcript generation and artifact wiring.
- Small pilot run with analysis tables.
- Short memo noting whether transcript memory helps or just adds prompt bloat.

## Acceptance Criteria

- Transcript generation is deterministic and does not require a model call.
- The transcript artifact is small, inspectable, and recorded in the run
  metadata.
- `diff_only + transcript` can be planned and executed from the same parent
  root as `diff_only`.
- The child prompt receives both the applied diff and the transcript artifact.
- The pilot can distinguish transcript value from diff value and from full
  snapshot value.

## Validation

Before any larger batch:

- inspect one generated transcript artifact directly,
- confirm it reflects the parent trajectory rather than a hand-authored note,
- confirm `diff_only` still fails cleanly when the diff does not apply,
- run a narrow pilot and build the analysis tables.

## Out Of Scope

- `command_replay`
- replaying shell history as an executor
- model-generated summaries
- changes to the snapshot selector
- changes to the root branch policy

## Status

Planned. This ticket should follow T007 and can reuse its diff-only plumbing
without reworking the filesystem side again.
