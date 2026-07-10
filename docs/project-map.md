# Project Map

This repo tests whether Go-Explore-style continuation can help coding agents solve Terminal-Bench tasks. Harbor runs the tasks, Daytona provides restorable sandboxes, and this repo adds snapshot and continuation logic.

## Top-Level Folders

| Path | Purpose |
| --- | --- |
| `go_explore/` | Main implementation: CLI, Harbor command building, snapshot hooks, continuation planning, result parsing. |
| `docs/` | Design notes, decisions, runbooks, and experiment writeups. Use this for durable reasoning. |
| `tasks/` | Local ticket system. Use `tasks/backlog.md` for status. |
| `tests/` | Unit and e2e tests. E2E tests may call Harbor, Docker, Daytona, or model APIs. |
| `benchmarks/` | Early benchmark integration code and experiments. |
| `jobs/` | Local Harbor outputs from runs. Not committed. Inspect this for traces, rewards, and failures. |

## Key Files

| Path | Purpose |
| --- | --- |
| `go_explore/cli.py` | CLI entry point: oracle runs, job summaries, cached tasks, continuation runs. |
| `go_explore/harbor.py` | Builds and runs `harbor run` commands. |
| `go_explore/results.py` | Reads Harbor `result.json` files into small summaries. |
| `go_explore/continuations.py` | Rebuilds root job config, plans snapshot continuation jobs, runs them, writes reports. |
| `go_explore/task_inventory.py` | Lists locally cached Harbor tasks. |
| `go_explore/agents/factory.py` | Harbor import-path factories for snapshot-aware agents. |
| `go_explore/agents/snapshot_agent.py` | Wraps Terminus-2, hooks command execution, creates live snapshot contexts. |
| `go_explore/snapshots/models.py` | Snapshot dataclasses and `/tmp/go_explore_context.md` path. |
| `go_explore/snapshots/policies.py` | Snapshot policies and early heuristic selector. |
| `go_explore/snapshots/manager.py` | Applies policy, calls backend, stores snapshot records. |
| `go_explore/snapshots/backends.py` | Daytona snapshot side effects. |
| `go_explore/snapshots/replay.py` | Replays saved ATIF trajectories through snapshot logic. |

## Snapshot-Aware Run Flow

1. User runs Harbor with `--agent-import-path go_explore.agents.factory:snapshot_aware_terminus2_factory`.
2. Harbor calls `factory.py`, which creates Terminus-2 and wraps it in `SnapshotAwareAgent`.
3. `SnapshotAwareAgent.run()` receives the live Harbor environment and Daytona sandbox.
4. The wrapper hooks Terminus-2 command execution.
5. After meaningful command batches, it builds a `SnapshotContext`.
6. `AsyncSnapshotManager` asks the policy whether this step should be saved.
7. `DaytonaSnapshotBackend` writes `/tmp/go_explore_context.md`, then creates a Daytona snapshot.
8. Harbor writes normal job artifacts under `jobs/<job-name>/`.

Important: for custom snapshot-aware runs, use `--agent-import-path` without also passing a built-in `--agent`.

## Continuation Run Flow

1. User runs `go-explore continue-from-snapshots jobs/<root-job> --job-prefix <prefix>`.
2. `cli.py` summarizes the root job and selects a root trial.
3. `continuations.py` rebuilds the root Harbor config from `jobs/<root-job>/config.json`.
4. If snapshots are not passed explicitly, it lists Daytona snapshots matching `go-explore-<trial-name>-step-`.
5. It builds one Harbor command per snapshot using `--ek snapshot_template_name=<snapshot-name>`.
6. With `--execute`, each command runs as a separate Harbor job.
7. The continuation report is written to `jobs/<root-job>/continuation-report.json`.

## Outputs To Inspect

| Path | Use |
| --- | --- |
| `jobs/<job>/config.json` | Harbor config used for the run. |
| `jobs/<job>/result.json` | Job-level trial counts, errors, and aggregate metrics. |
| `jobs/<job>/<trial>/result.json` | Trial reward, task name, and exception info. |
| `jobs/<job>/<trial>/agent/trajectory.json` | Terminus-2 ATIF trajectory when traces are exported. |
| `jobs/<root-job>/continuation-report.json` | Go-Explore lineage report for continuation branches. |

## Stable Vs Experimental

Stable enough to build on:

- `HarborRunConfig` and `build_harbor_command()`
- `summarize_job()`
- snapshot model/policy/manager boundaries
- continuation planning/reporting boundaries

Still experimental:

- snapshot scoring and selection,
- live Terminus-2 hook details,
- Daytona snapshot lifecycle and cleanup,
- parent context summarization passed to child agents.

## Open Questions

- Should snapshot metadata be persisted locally beyond Daytona snapshot names?
- Should continuation agents receive full trajectory context, a compressed summary, or only the original task?
