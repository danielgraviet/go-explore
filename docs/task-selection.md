# Task Selection

We are starting from Harbor-registered Terminal-Bench tasks, not custom tasks.

## Confirmed Harbor Datasets

The Harbor registry includes:

- `terminal-bench@2.0`: 89 tasks.
- `terminal-bench-sample@2.0`: 10 tasks.

Use the sample dataset for smoke tests, then move to the full dataset once the run loop is stable.

## First Candidate Tasks

These are good first candidates because they are medium difficulty, have bounded timeouts, and should produce useful intermediate progress signals.

| Task | Difficulty | Category | Why it is useful |
| --- | --- | --- | --- |
| `openssl-selfsigned-cert` | medium | security | Clear file outputs, deterministic verification, easy to reason about partial progress. |
| `regex-log` | medium | data-processing | Likely produces inspect/edit/test loops without heavyweight services. |
| `large-scale-text-editing` | medium | file-operations | Tests command-line editing and partial transformation quality. |
| `git-leak-recovery` | medium | software-engineering | Good fit for snapshotting because useful state accumulates through git inspection. |
| `reshard-c4-data` | medium | data-science | More complex coding task with scripts, tests, and likely non-trivial iteration. |

Keep one easier task available for infrastructure debugging:

- `fix-git`
- `overfull-hbox`
- `hello-world`

Avoid hard or long-timeout tasks until the snapshot loop works.

## Commands

Print a Harbor oracle command without executing it:

```bash
python -m go_explore.cli oracle-run --dataset terminal-bench-sample@2.0 --n-tasks 1 --n-concurrent 1 --job-name oracle-smoke
```

Run the same command:

```bash
python -m go_explore.cli oracle-run --dataset terminal-bench-sample@2.0 --n-tasks 1 --n-concurrent 1 --job-name oracle-smoke --execute
```

Run the same smoke path in Daytona, loading `DAYTONA_API_KEY` from `.env`:

```bash
set -a; source .env; set +a
harbor run --agent oracle --env daytona --jobs-dir jobs --n-attempts 1 --n-concurrent 1 --dataset terminal-bench-sample@2.0 --n-tasks 1 --job-name daytona-oracle-smoke --export-traces
```

Summarize a Harbor job result:

```bash
python -m go_explore.cli summarize-job jobs/oracle-smoke
```

List locally cached Harbor task metadata:

```bash
python -m go_explore.cli list-cached-tasks
```

## Current Runtime Finding

The first oracle smoke run resolved `terminal-bench-sample@2.0` and selected `chess-best-move`, but failed before agent execution because Docker was not running:

```text
Cannot connect to the Docker daemon at unix:///Users/danielgraviet/.docker/run/docker.sock
```

Harbor still wrote structured results under `jobs/oracle-smoke/`, which confirms job summaries are available even when traces are unavailable or the trial fails during setup.

One additional finding: Harbor reports that the `oracle` agent does not export ATIF traces. For oracle runs, use `result.json` and trial result files as the first analysis source.

## Daytona Smoke Result

`daytona-oracle-smoke` completed successfully against `terminal-bench-sample@2.0`:

```text
trials: 1/1
errors: 0
mean: 1.0
task: chess-best-move
reward: 1.0
```

The saved trial result confirms Harbor used `environment.type = "daytona"`.

## Next Hook To Inspect

Once Docker is running and one oracle task completes, inspect:

- `jobs/<job-name>/result.json`
- `jobs/<job-name>/<trial-name>/result.json`
- `jobs/<job-name>/<trial-name>/trial.log`
- any non-oracle trajectory files produced by a real agent

The snapshot integration should be inserted at the lowest Harbor layer that can observe agent commands and environment mutations. If Harbor does not expose that cleanly, the next move is a custom Harbor agent or environment wrapper.

## Next Implementation Sequence

1. Run one non-oracle agent on Daytona with traces enabled.
2. Inspect whether Harbor emits per-command or per-turn artifacts for that agent.
3. Identify the hook point for snapshot events:
   - agent wrapper if we only need turn boundaries,
   - environment wrapper if we need command/file mutation boundaries,
   - Daytona-specific integration if we need cloud fork/restore primitives.
4. Add a snapshot recorder that writes durable metadata beside each Harbor trial.
5. Add a continuation runner that can start from a selected snapshot instead of the original task environment.
6. Compare baseline attempts from scratch against continuation attempts from selected snapshots.
