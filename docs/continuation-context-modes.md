# Continuation Context Modes

This spec defines the start-state and context modes needed to test whether
continuation helps because of the full sandbox, the inherited prompt context,
or both.

The current implementation supports two parent-summary channels:

- boot a Daytona sandbox from `snapshot_template_name=<snapshot>` and let
  `SnapshotAwareAgent` read `/tmp/go_explore_context.md` from that sandbox;
- start from a clean Harbor/Daytona environment and pass
  `parent_context_path=<parent-trial>/agent/trajectory.json` so
  `SnapshotAwareAgent` can inject a host-side summary of the parent trajectory.

That default is useful, but it confounds two effects:

- **environment reuse**: files, dependencies, caches, services, build outputs,
  logs, and other sandbox state are preserved;
- **memory transfer**: the child receives text about what the parent tried.

The experiments in `docs/essay.md` need to separate those effects.

## Shared Fields

Every planned continuation or baseline run should record:

| Field | Meaning |
| --- | --- |
| `start_state_type` | How the child environment is initialized. |
| `context_mode` | What parent text, if any, is added to the task prompt. |
| `parent_job_dir` | Root job path when the run derives from a parent. |
| `parent_trial_name` | Parent trial name when applicable. |
| `parent_snapshot` | Daytona snapshot name when applicable. |
| `parent_artifacts` | Paths to diff, transcript, command log, or replay manifest when used. |

Use `null` for fields that do not apply. Do not imply a parent snapshot exists
for modes that start from a clean environment.

## Claim 1 Mapping

`docs/essay.md` frames Claim 1 around fixed-parent, fixed-budget child
conditions. Represent those conditions with these mode pairs:

| Essay condition | `start_state_type` | `context_mode` |
| --- | --- | --- |
| Fresh restart | `clean` | `original_task_only` |
| Diff only | `diff_only` | `original_task_only` |
| Diff + transcript summary | `diff_only` | `full_transcript_summary` |
| Diff + command log | `diff_only` | `command_log` |
| Replayed environment | `command_replay` | `original_task_only` |
| Full snapshot | `full_snapshot` | `parent_summary`, `original_task_only`, or `none` |

The first Phase 3 implementation should record these fields even when the
underlying executor still only supports a subset. That lets reports distinguish
"not implemented" from "implemented and failed."

## Modes

### Original Task Only

| Property | Value |
| --- | --- |
| `start_state_type` | `clean` |
| `context_mode` | `original_task_only` |
| Inputs | Original Harbor task config only. |
| Expected artifacts | Normal Harbor job artifacts; no parent diff, transcript, or snapshot required. |
| Current status | Available as ordinary Harbor run, not yet represented as an experiment mode. |
| Immediate target | Yes, for P3-T002. |

This is the clean restart baseline. The child sees the original task and a
fresh environment. It should not receive parent summaries, prior commands, or
parent edits.

Likely failure modes:

- repeats all setup and discovery work,
- solves by chance and makes continuation look less useful if budget is not
  controlled,
- can be incorrectly compared against continuation if it receives more tokens.

### Parent Summary

| Property | Value |
| --- | --- |
| `start_state_type` | `full_snapshot` or `clean` |
| `context_mode` | `parent_summary` |
| Inputs | Full snapshot plus `/tmp/go_explore_context.md`, or clean environment plus parent `trajectory.json`. |
| Expected artifacts | For full snapshots: `archive.json`, `events.jsonl`, continuation report, and sandbox context file captured in the snapshot. For clean starts: parent trajectory path recorded in `parent_artifacts`. |
| Current status | Implemented as explicit `context_mode=parent_summary` for full-snapshot and clean-start plans. |
| Immediate target | Yes, keep as the default full-snapshot continuation mode. |

For full snapshots, `DaytonaSnapshotBackend` writes a trajectory summary to
`/tmp/go_explore_context.md` before snapshotting. A resumed
`SnapshotAwareAgent` downloads that file and appends it to the task instruction.
For the clean parent-summary baseline, the planner passes the parent
`trajectory.json` path as an agent kwarg and `SnapshotAwareAgent` injects a
compact host-side summary before the child starts.

Likely failure modes:

- **context misuse**: the child trusts a wrong parent conclusion;
- wrong answer rubber-stamping, as seen in the chess run where the child read
  the parent work and stopped after only a few steps;
- summary may omit uncertainty, failed hypotheses, or verifier status.

Implementation constraint:

- Keep this mode explicit in manifests/events as `context_mode=parent_summary`
  so it can be compared against disabled and critical context modes.
- For clean starts, `snapshot_name` and `parent_snapshot` must remain `null`;
  the recorded parent trajectory path is evidence of text transfer, not
  restored environment state.

### Full Transcript Summary

| Property | Value |
| --- | --- |
| `start_state_type` | `clean` or `full_snapshot` |
| `context_mode` | `full_transcript_summary` |
| Inputs | Parent `trajectory.json` or a generated summary derived from it. |
| Expected artifacts | Parent transcript path and summary artifact path. |
| Current status | Partially available: ATIF trajectory can be read, but no standalone summary mode exists. |
| Immediate target | No; defer until clean/full snapshot baselines are stable. |

This mode tests whether text memory alone explains the benefit. The child gets a
summary of the full parent transcript, but may or may not get the parent
environment depending on `start_state_type`.

Likely failure modes:

- inherits stale or overconfident narration,
- misses environment facts not captured in the transcript,
- summary generation can add cost and nondeterminism if model-generated.

### Diff Only

| Property | Value |
| --- | --- |
| `start_state_type` | `diff_only` |
| `context_mode` | `original_task_only` |
| Inputs | Clean environment plus parent git diff. |
| Expected artifacts | Diff file, clean run job, and manifest linking the diff to the parent run. |
| Current status | Implemented (T007): `SnapshotAwareAgent.setup` applies the parent diff via `git apply` before the agent's first turn; a failed apply raises `DiffApplyFailed` so it is recorded as an executor failure, not a task failure. |
| Immediate target | Yes, for P3-T002 as the first compressed-state comparator. |

This mode applies the parent's code changes to a clean environment but does not
preserve installed dependencies, caches, generated files, services, logs, or
parent text.

Likely failure modes:

- diff does not apply cleanly,
- parent progress lived outside git-tracked files,
- child must redo setup and test reproduction.

Implementation constraint:

- If applying the diff is not reliable in P3-T002, create a manifest-level
  scaffold and a follow-up executor ticket rather than broadening scope.

### Diff Plus Transcript

| Property | Value |
| --- | --- |
| `start_state_type` | `diff_only` |
| `context_mode` | `full_transcript_summary` |
| Inputs | Clean environment, parent git diff, and parent transcript summary. |
| Expected artifacts | Diff file, transcript/summary file, and manifest linking both to the parent. |
| Current status | Implemented (T008): `plan_start_state_baselines(..., diff_only_context_mode="full_transcript_summary")` writes a deterministic, rule-based transcript (`go_explore/snapshots/transcript.py`, no model call) alongside the diff, and attaches it via `parent_context_path`. `SnapshotAwareAgent` injects it with an explicit "not a model-generated narrative, verify yourself" disclaimer. |
| Immediate target | Yes - this is the Claim 1 compressed-memory comparator. |

This mode tests a strong compressed baseline: code state plus text memory, but
without preserving the full sandbox.

Likely failure modes:

- combines diff-application failures with context misuse,
- can look artificially strong if summary cost is not counted,
- can hide that runtime state was missing until the child reruns tests.

### Diff Plus Command Log

| Property | Value |
| --- | --- |
| `start_state_type` | `diff_only` |
| `context_mode` | `command_log` |
| Inputs | Clean environment, parent git diff, and parent command log. |
| Expected artifacts | Diff file, command-log file, and manifest linking both to the parent. |
| Current status | Implemented (T009): `plan_start_state_baselines(..., diff_only_context_mode="command_log")` writes a deterministic, ordered command+output log (`go_explore/snapshots/command_log.py`, no model call, no replay execution) alongside the diff, and attaches it via `parent_context_path`. Distinct in shape from `full_transcript_summary`: entries are grouped by ATIF step (command batch + its one observed terminal excerpt, harness retry/formatting boilerplate stripped) rather than categorized into narrative sections - the most explicit compressed-memory condition short of actually replaying the commands. Not to be confused with `command_replay` below, which would *execute* the parent's commands again; this only shows their record. |
| Immediate target | Yes - this is the Claim 1 exact-memory comparator, alongside `full_transcript_summary`. |

This mode tests whether giving the child the literal setup/discovery sequence
(not a summary of it) is enough to recover missing sandbox state, and how
that compares against a categorized summary of the same trajectory.

Likely failure modes:

- same diff-application and context-misuse risks as diff + transcript,
- longer prompts than transcript summary for the same trajectory, so any
  advantage must be weighed against added token cost,
- batched-command steps share one terminal excerpt, so the log can't always
  attribute an observed effect to one specific command in a multi-command
  turn.

### Command Replay

| Property | Value |
| --- | --- |
| `start_state_type` | `command_replay` |
| `context_mode` | `original_task_only` (always - this arm is about environment state, not text memory) |
| Inputs | Fresh (`clean`) sandbox plus a replay manifest of allowlisted parent commands. |
| Expected artifacts | Replay manifest (`replay-manifest.json`, plan-time: selected/skipped commands with reasons) and replay result (`replay-result.json`, sandbox-side: per-command replayed/failed status, output excerpts, total replay seconds). |
| Current status | Implemented (T010): `plan_start_state_baselines(start_state_types=("command_replay",))` writes the plan-time manifest via `go_explore/snapshots/command_replay.py`'s conservative selector (dependency-install commands only, deduplicated, rejected if they contain shell metacharacters, capped at `--replay-max-commands`). `SnapshotAwareAgent.setup` execs the planned commands in the fresh sandbox best-effort - a failed or skipped command never raises or blocks the agent, since replay is inherently an approximation, not a guarantee. |
| Immediate target | Yes - this is the Claim 1 environment-reconstruction comparator against `full_snapshot`. |

This mode tries to recreate useful environment state by rerunning setup or
discovery commands. It is a useful comparator for full snapshots because it
tests whether exact sandbox restore is necessary.

Likely failure modes:

- commands are not idempotent,
- network/package versions drift,
- services or background processes are not reconstructed,
- replay can be slower than snapshot restore,
- dangerous or compound commands must be filtered before replay - and the
  narrow selector means many real-world install commands (e.g. wrapped in
  `cd X && pip install Y | tail -20`) get correctly rejected rather than
  replayed, so this arm's coverage is inherently partial by design.

Implementation constraint (honored):

- Command replay starts with a conservative allowlist (dependency installs
  only) and does not blindly replay arbitrary shell history. Broadening the
  allowlist (build commands, service starts) is an explicit follow-up, not
  part of this first cut.

### Full Snapshot

| Property | Value |
| --- | --- |
| `start_state_type` | `full_snapshot` |
| `context_mode` | `none`, `original_task_only`, `parent_summary`, or `critical_parent_summary` |
| Inputs | Daytona snapshot name. |
| Expected artifacts | Parent archive entry, `snapshot_selected` event, `continuation_started` event, child Harbor job. |
| Current status | Explicit `parent_summary`, `none`, and `critical_parent_summary` modes are implemented. |
| Immediate target | Yes, with explicit context-mode recording. |

This is the main Go-Explore state representation: fork the exact sandbox from a
saved Daytona snapshot.

Likely failure modes:

- snapshot no longer exists in Daytona,
- restore succeeds but inherited text causes context misuse,
- saved state is already wrong or too close to a dead end,
- snapshot overhead outweighs preserved work.

Implementation constraint:

- P3-T002 should support full snapshot with `context_mode=parent_summary` and,
  if practical, full snapshot with context disabled. The disabled-context mode
  is the cleanest way to measure environment value alone.
- Use `context_mode=critical_parent_summary` when the parent root failed, timed
  out, or has unknown reward. The child still receives parent history, but the
  prompt frames restored files and prior reasoning as untrusted evidence that
  must be independently audited.

## Context Misuse And Wrong-Parent-State Failures

The chess failure in `docs/archive-docs/results.md` is the canonical example.
The parent wrote a wrong answer, the child restored that state, read the parent
summary, trusted it, and quickly declared completion. A fresh attempt would at
least have tried to solve the task.

Track these as a separate failure class:

| Signal | Interpretation |
| --- | --- |
| Child stops much sooner than parent after reading parent context | Possible rubber-stamping. |
| Child repeats parent final answer without independent validation | Context misuse. |
| Parent verifier failed but child prompt implies useful prior work | Bad memory transfer. |
| Full snapshot with no parent context succeeds where parent-summary mode fails | Environment useful, memory harmful. |

Prompt text should avoid implying that parent work was correct. Future context
summaries should include uncertainty and verifier status when available.

## Phase 3 Implementation Targets

Implement these first:

1. `clean` + `original_task_only`
2. `diff_only` + `original_task_only`
3. `full_snapshot` + `parent_summary`
4. `full_snapshot` + `original_task_only` or `none`, if disabling context can be
   done without invasive agent changes
5. `clean` + `parent_summary`

Defer these until after the first pilot:

- `full_transcript_summary`
- `diff_only` + `full_transcript_summary`
- `command_replay`

## Notes

- Start-state mode and context mode are separate dimensions. Keep them separate
  in manifests, events, and reports.
- Count summary generation and replay work as budget when those modes are
  implemented.
- Do not treat a restored snapshot as proof that the state is useful. Selection
  quality and context transfer need separate measurements.
