# Go-Explore Snapshot-Aware Agent Wrapper

This module provides a lightweight wrapper around Harbor agents that captures snapshots during live execution using Daytona.

## Architecture

```
Harbor CLI
    ↓
SnapshotAwareAgent (wrapper)
    ├─ Wraps any BaseAgent (Terminus-2, Oracle, Claude-Code, etc.)
    │
    └─ On perform_task():
       1. Hooks agent's _execute_commands method
       2. Captures bash commands and terminal output
       3. Feeds to AsyncLiveSnapshotSession
       4. Session evaluates via EveryAgentStepPolicy
       5. Daytona creates a snapshot for each agent step
       6. Metadata stored for later continuation
```

## Files

- **`snapshot_agent.py`**: Core `SnapshotAwareAgent` class that wraps any Harbor agent
- **`factory.py`**: Pre-built factory functions for common agent types (Terminus-2, Oracle)
- **`example_usage.md`**: CLI examples for running with Harbor
- **`README.md`**: This file

## Quick Start

### 1. Run Terminus-2 with Snapshot Capture

```bash
harbor run \
  --agent go_explore.agents.factory:SnapshotAwareTerminus2 \
  --model anthropic/claude-haiku-4-5-20251001 \
  --env daytona \
  --dataset terminal-bench-sample@2.0 \
  --n-tasks 1 \
  --job-name snapshot-test-1
```

### 2. Check Captured Snapshots

Snapshots are stored with Daytona and their IDs are logged during execution. After the run:

```bash
# Snapshots are available via Daytona API
# IDs are named: go-explore-{trial_name}-step-{step_num}
```

### 3. Restore from Snapshot (Future)

Once continuation logic is implemented:

```python
# Pseudocode
snapshot_id = "go-explore-fix-git__abc123-step-5"
forked_sandbox = await daytona.fork(snapshot_id)
# Run new agent attempt from forked state
```

## How Snapshots Are Triggered

The live wrapper snapshots every agent command batch:

1. Capture the commands and terminal output for a step
2. Build a `SnapshotContext`
3. Feed the context into `EveryAgentStepPolicy`
4. Create a Daytona snapshot for that step

## Implementation Details

### Method Hooking

The wrapper works by:

1. Storing reference to wrapped agent
2. On `perform_task()`, patching the agent's `_execute_commands` method
3. After the original method runs, capturing commands + output
4. Converting to `SnapshotContext` and feeding to snapshot session

### Async Handling

- Snapshot processing is async (uses Daytona API)
- Wrapped in `asyncio.run()` to execute from sync context
- Failures logged but don't block agent execution

### Trial Name

Trial name is derived from the TmuxSession name, which Harbor sets uniquely per trial.

## Configuration

The `SnapshotAwareAgent` accepts:

```python
SnapshotAwareAgent(
    wrapped_agent: BaseAgent,      # The agent to wrap
    sandbox: Any = None,            # Daytona AsyncSandbox (from Harbor)
    # inherited from BaseAgent:
    version: str | None = None,
    prompt_template: str | None = None,
    **kwargs
)
```

## Extending

### Custom Policy

To use a different policy (not `EveryAgentStepPolicy`):

1. Modify `snapshot_agent.py` line ~57 to use a different policy
2. Or make it configurable via kwargs

### Custom Backend

To use something other than `DaytonaSnapshotBackend`:

1. Modify `snapshot_agent.py` lines ~54-62
2. Pass different backend class/instance

### New Agent Type

To wrap a new agent type:

1. Create factory function in `factory.py`
2. Call `create_snapshot_aware_<agent_name>()`
3. Use the factory import path as the `--agent` value to invoke from Harbor

## Debugging

Enable debug logging:

```bash
export DEBUG=1
harbor run --agent go_explore.agents.factory:SnapshotAwareTerminus2 --debug
```

If snapshots fail, check Harbor logs for warnings like:
```
Warning: Snapshot processing failed: ...
```

These don't block the agent—they just log and continue.

## Limitations

1. **Sync/Async boundary**: Uses `asyncio.run()` which can be problematic in some contexts
2. **Policy is fixed**: `EveryAgentStepPolicy` is hardcoded for the MVP
3. **Command capture**: Only captures bash commands, not other tool types
4. **Terminal state**: Only captures text output, not full visual state

## Future Work

1. Make policy configurable via kwargs
2. Make backend configurable
3. Implement continuation runner (fork + resume)
4. Implement snapshot ranking and selection
5. Add metrics tracking (cost, tokens, timing)
6. Support other agent types (Claude-Code, Cursor, etc.)
7. Add telemetry/analytics for snapshot utility
