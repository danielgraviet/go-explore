# Daytona Snapshot Hook Bug

This note records the bug that made the Daytona snapshotting e2e look like it was running the snapshot-aware agent while no snapshots were created.

## Symptom

The `terminus-2` Daytona run succeeded and wrote a normal ATIF trajectory, but Daytona showed no snapshots with the expected `go-explore-<trial>-step-*` prefix.

Observed behavior:

- Harbor job succeeded with `reward=1.0`.
- `jobs/<job>/<trial>/agent/trajectory.json` contained agent steps and shell tool calls.
- `investigate_tbench_hooks.py` showed snapshot-eligible command batches under `tool_calls[*].arguments.keystrokes`.
- Daytona snapshot listing returned no names matching the trial prefix.
- Debug flags such as `--ak hooks_debug=true` produced no wrapper logs.

That combination meant the command stream existed, but our snapshot wrapper was not actually in the live execution path.

## Root Cause

The Harbor command passed both:

```bash
--agent terminus-2
--agent-import-path go_explore.agents.factory:SnapshotAwareTerminus2
```

For Harbor `jobs`, the agent factory checks the named agent first. If `config.agent.name` is set to a valid built-in agent name, Harbor instantiates that built-in agent and never uses `config.agent.import_path`.

The saved job config still showed the import path, which was misleading:

```json
{
  "name": "terminus-2",
  "import_path": "go_explore.agents.factory:SnapshotAwareTerminus2"
}
```

But the actual instantiated agent was Harbor's built-in `terminus-2`, not `SnapshotAwareAgent`.

There was a second mismatch: the original snapshot wrapper was shaped around the older `terminal_bench` sync agent API. The live Harbor agent is `harbor.agents.terminus_2.Terminus2`, which uses async `setup()` and `run()` and executes commands through async `_execute_commands()`.

## Fix

The fix has two parts.

First, custom import-path runs must omit `--agent`:

```bash
harbor run \
  --env daytona \
  --jobs-dir jobs \
  --n-attempts 1 \
  --n-concurrent 1 \
  --dataset terminal-bench@2.0 \
  --model anthropic/claude-haiku-4-5-20251001 \
  --include-task-name fix-git \
  --job-name <job-name> \
  --agent-import-path go_explore.agents.factory:SnapshotAwareTerminus2
```

`HarborRunConfig.agent` now accepts `None`, and `build_harbor_command()` skips `--agent` when it is `None`.

Second, the snapshot-aware factory now wraps Harbor's actual async `Terminus2` class. The wrapper delegates `setup()` and `run()`, initializes its Daytona backend from `environment._sandbox`, and hooks the wrapped agent's async `_execute_commands()` method. That hook sees the real command batch and terminal output for each agent step.

## Files To Inspect

- `go_explore/harbor.py`
  - `HarborRunConfig.agent: str | None`
  - `build_harbor_command()` omits `--agent` for import-path-only runs.

- `go_explore/agents/factory.py`
  - `SnapshotAwareTerminus2`
  - `create_snapshot_aware_terminus2()` imports `harbor.agents.terminus_2.Terminus2`.
  - Harbor-provided `logs_dir`, `model_name`, and `logger` are passed to the wrapped agent.

- `go_explore/agents/snapshot_agent.py`
  - `SnapshotAwareAgent.setup()`
  - `SnapshotAwareAgent.run()`
  - `_ensure_snapshot_session()` initializes from the real Daytona sandbox.
  - `_hook_agent_loop()` wraps async `_execute_commands()` and snapshots each command batch.

- `tests/e2e/test_daytona_oracle.py`
  - `test_daytona_terminus2_with_snapshotting_command_runs_successfully()`
  - Uses the custom factory import path as the `--agent` value.
  - Verifies Daytona snapshots exist after the run.

- `tests/test_harbor.py`
  - Guards the command builder against reintroducing the built-in `terminus-2` agent when the snapshot wrapper is required.

- `investigate_tbench_hooks.py`
  - Parses ATIF trajectories and prints command batches under `tool_calls[*].arguments.keystrokes`.

## Verification

The corrected direct probe created real Daytona snapshots:

```text
go-explore-fix-git__fGHHE5b-step-0
go-explore-fix-git__fGHHE5b-step-1
go-explore-fix-git__fGHHE5b-step-2
go-explore-fix-git__fGHHE5b-step-3
go-explore-fix-git__fGHHE5b-step-4
```

The focused e2e passed:

```bash
pytest tests/e2e/test_daytona_oracle.py::test_daytona_terminus2_with_snapshotting_command_runs_successfully -q --run-e2e
```

Result:

```text
1 passed in 231.59s
```

Cheap regression tests also passed:

```bash
pytest tests/test_harbor.py tests/test_snapshot_agent.py -q
```

Result:

```text
10 passed
```

## Takeaway

When using Harbor `jobs` with a custom agent factory, do not pass a built-in `--agent` name at the same time. The import path may still appear in the saved config, but Harbor will instantiate the built-in agent first. For snapshotting, the reliable hook point is Harbor Terminus-2's async `_execute_commands()` method, after the Daytona environment has started and exposed the real sandbox object.
