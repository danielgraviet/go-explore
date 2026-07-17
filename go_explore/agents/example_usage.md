# Using the Snapshot-Aware Agent with Harbor

The `SnapshotAwareAgent` wraps any Harbor agent and automatically captures snapshots during execution using Daytona's `_experimental_create_snapshot` API.

## Usage with Harbor CLI

### Basic Example: Wrapping Terminus-2

Use the pre-built factory function from `go_explore.agents.factory`:

```bash
harbor run \
  --agent-import-path go_explore.agents.factory:SnapshotAwareTerminus2 \
  --model anthropic/claude-haiku-4-5-20251001 \
  --env daytona \
  --dataset terminal-bench-sample@2.0 \
  --n-tasks 3 \
  --job-name go-explore-test
```

### Example: Wrapping Oracle

```bash
harbor run \
  --agent-import-path go_explore.agents.factory:SnapshotAwareOracle \
  --env daytona \
  --dataset terminal-bench-sample@2.0 \
  --n-tasks 3 \
  --job-name go-explore-oracle-test
```

### Snapshot Policy Option

The wrapper accepts snapshot policy kwargs through Harbor's agent kwarg flag:

```bash
harbor run \
  --agent-import-path go_explore.agents.factory:SnapshotAwareTerminus2 \
  --model anthropic/claude-haiku-4-5-20251001 \
  --ak snapshot_policy=every_step \
  --env daytona \
  --dataset terminal-bench-sample@2.0 \
  --n-tasks 3 \
  --job-name go-explore-every-step
```

## How It Works

1. **Agent Wrapping**: The `SnapshotAwareAgent` wraps any Harbor agent (oracle, terminus-2, claude-code, etc.)
2. **Hook Installation**: On `perform_task()`, the wrapper hooks into the wrapped agent's `_execute_commands` method
3. **Step Capture**: After each command batch executes, the wrapper:
   - Captures the executed bash commands
   - Captures the terminal output
   - Creates a `SnapshotContext` from the step data
   - Feeds it to `AsyncLiveSnapshotSession` for policy evaluation
4. **Snapshot Creation**: The MVP policy snapshots every agent step, so Daytona creates a snapshot for each command batch
5. **Storage**: Snapshot IDs and metadata are stored for later continuation

## Snapshots Are Created For

The current MVP policy snapshots every agent command batch. The selective heuristic policy remains available for offline ranking and future experiments.

## Architecture Notes

- The wrapper is **transparent** to Harbor—it looks like a normal agent
- The **sandbox object** is passed through Harbor's `--ak` (agent kwargs) mechanism
- **Snapshots are async**, but executed via `asyncio.run()` to work in the sync agent context
- If snapshotting fails, it logs a warning but **doesn't block** agent execution

## Next Steps

1. Test with a simple terminal-bench task
2. Implement continuation logic: fork from snapshots and resume
3. Implement snapshot ranking and selection
4. Measure go-explore impact on success rate vs. independent attempts
