# Research Questions

These questions were migrated from the original root `todo.md`. They are not tickets by themselves; turn them into tickets when the next concrete action is clear.

## Go-Explore Selection

- Does the Go-Explore algorithm select all novel states and explore from them, or does it use a trained model to select only a few?
- What is the minimum useful snapshot selection policy for Phase 1: every step, first N, heuristic ranking, or learned interestingness?

## Snapshot Value

- Do snapshots from every agent action contain meaningfully different states or dependencies?
- If an agent only runs a read-only command like `ls`, is the snapshot useful enough to keep?
- Which actions most often produce valuable continuation states: dependency installation, file edits, test runs, discovery commands, or partial fixes?

## Manual Restore Path

- For early stages, can we run one Harbor job until failure, inspect collected snapshots, manually choose one checkpoint, restore from it, and see whether the task can be solved?
- Should the first proof of value be manual before automating the full loop?

## Daytona Runtime Behavior

- Do Daytona snapshots interrupt the main agent path?
- Is the agent paused while snapshot creation is in progress?
- How much wall-clock overhead does snapshot creation add per step?

## Continuation Context

- How can we increase the chance that exploration from a snapshot succeeds?
- Should child agents receive a summary of what happened before the snapshot?
- Should child agents receive the original task only, the full parent transcript, a compressed failure summary, or selected context?
- Does continuation mainly help by preserving environment work, such as installed dependencies, or by giving the next agent a better search location?
