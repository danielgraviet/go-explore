# T010 — Implement replayed environment

## Goal

Add the `command_replay` / replayed-environment condition from
`docs/essay.md` as a real experiment arm. The child should receive:

- a fresh sandbox,
- a replay plan derived from the parent trajectory,
- a conservative sequence of setup/discovery commands that are replayed
  before the child starts solving.

This is the environment-side comparator for Claim 1. It tests whether the
benefit of full snapshots comes from exact sandbox state, or whether the same
state can be rebuilt cheaply enough by rerunning the right commands.

## Problem

We already have:

- clean child starts,
- parent trajectory logs,
- ATIF parsing and signal extraction,
- diff application for `diff_only`,
- full snapshot continuations.

What is missing is the executor path that replays selected parent commands in a
new sandbox and records the replay outcome in a way that analysis can compare
against `clean`, `diff_only`, and `full_snapshot`.

Do **not** treat this as a blind shell-history replay. That would be brittle
and unsafe. The implementation should be conservative and allowlisted.

## Implementation Plan

### 1. Define the replay artifact

Create a replay manifest derived from the parent trajectory. It should record:

- the parent job and trial,
- the selected commands to replay,
- whether each command was replayed, skipped, or failed,
- command outputs or hashes when needed for audit,
- a final replay status,
- the parent artifact path used to generate the plan.

Keep it machine-readable and inspectable.

### 2. Build a conservative command selector

Use the existing ATIF helpers to extract candidate commands from
`trajectory.json`, then filter them down to commands that are likely to help a
fresh child rebuild useful state.

Prefer commands like:

- dependency installs,
- environment setup,
- service start commands,
- build commands,
- test reproduction commands.

Avoid or skip commands that are:

- destructive,
- non-idempotent,
- obviously task-solution-specific,
- interactive without a safe replay shape,
- dependent on live secrets or external state.

The selector should start narrow. A small allowlist is better than an overly
ambitious general replay system.

### 3. Execute replay in a clean sandbox

Add an executor path that:

- starts from `clean`,
- replays the selected commands in order,
- captures whether replay succeeded,
- records replay overhead separately from child solve time,
- fails cleanly if replay cannot be completed.

The child agent should still begin from the fresh sandbox after replay. This
arm is about reconstructing environment state, not carrying forward text.

### 4. Record the replay lineage

Make sure the planned run records:

- `start_state_type=command_replay`,
- `context_mode=original_task_only` for the main replay arm,
- `parent_artifacts` pointing at the replay manifest and any extracted
  command log,
- replay status in the execution report and analysis rows.

### 5. Keep the replay budget bounded

Replay can easily become more expensive than snapshot restore if it is not
trimmed. Bound it by:

- command count,
- timeout per command,
- total replay wall-clock,
- replayed command allowlist.

If replay becomes too expensive or brittle, stop and record that clearly.

### 6. Add a small pilot

Run the arm on tasks where setup state is plausibly reusable:

- `build-cython-ext`
- `pypi-server`
- `qemu-startup`

Compare:

- `clean`,
- `diff_only`,
- `diff_only + transcript`,
- `diff_only + command_log`,
- `command_replay`,
- `full_snapshot`.

## Deliverables

- Replay manifest format.
- Conservative command selector.
- Executor path for replayed environments.
- Unit tests for replay selection and failure handling.
- Narrow pilot run with analysis tables.
- Short memo on whether replay reconstructs enough useful state to compete
  with full snapshots.

## Acceptance Criteria

- Replay runs from a clean sandbox, not from a snapshot.
- Only allowlisted commands are replayed.
- Replay failures are recorded distinctly from task failures.
- The replay arm can be planned, executed, and analyzed alongside the other
  Claim 1 conditions.
- The pilot shows whether replayed setup is a credible substitute for full
  snapshots or just an expensive approximation.

## Validation

Before any larger batch:

- inspect one replay manifest directly,
- confirm skipped commands are intentional,
- confirm destructive commands are not replayed,
- run a single-task pilot and verify the replay overhead is separately
  accounted for.

## Out Of Scope

- `diff_only` text memory arms
- model-generated summaries
- unrestricted shell-history replay
- changes to the snapshot selector
- changes to the root branch policy

## Status

Planned. This ticket should be approached only after the diff-based text-memory
arms are in place so the replayed-environment result can be interpreted
against the compressed baselines and the full snapshot baseline.
