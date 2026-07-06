# Snapshot Strategy

We should treat snapshotting as a replaceable policy:

```text
snapshot_policy(step_context) -> list[SnapshotCandidate]
```

The policy should be pure where possible. The actual snapshot side effect belongs in a separate manager that receives a candidate, asks the environment backend to save/fork state, and records the returned restore reference.

## Inputs We Have Today

From Terminus-2 `trajectory.json`, each agent step can include:

- agent message,
- shell tool calls,
- terminal observations,
- model name,
- per-step token and cost metrics.

From trial results, we also get:

- final reward,
- verifier output,
- task name,
- environment type,
- timing information.

We do not yet have passing/failing tests at each intermediate step unless the agent explicitly runs tests or Harbor exposes per-command verifier hooks later.

## Policy Options

### Every Agent Step

Snapshot after each agent step.

Pros:

- very simple,
- robust to unknown task structure,
- captures all meaningful agent decisions,
- good baseline for early experiments.

Cons:

- can bloat quickly on long-horizon tasks,
- many states will be low value,
- snapshot cost scales directly with agent episode count.

Use this first as the baseline policy.

### Interesting Agent Step

Snapshot only when trajectory content suggests state changed or new information was discovered.

Initial signals:

- file edits,
- git state transitions,
- test commands,
- verifier-like output,
- conflicts, errors, tracebacks, or exceptions,
- task completion markers.

Pros:

- much cheaper than snapshotting every step,
- easy to reason about,
- works with current `trajectory.json` artifacts.

Cons:

- heuristic and task-biased,
- can miss useful planning states,
- does not understand novelty deeply.

Use this as the first practical policy once the baseline is measured.

### Budgeted Reservoir

Snapshot every step at first, then keep only the top `k` states under a score and diversity rule.

Pros:

- bounded storage,
- can combine simple heuristics with novelty,
- avoids committing to a perfect online decision.

Cons:

- may require deleting cloud snapshots,
- needs a stable scoring function,
- harder to debug than every-step.

This is probably the right MVP policy after the first proof of restore/fork works.

### Learned Interestingness

Use an LLM or trained classifier to decide whether a state is novel, promising, or worth resuming from.

Possible inputs:

- recent trajectory window,
- current diff,
- command history,
- test/verifier output,
- failure mode,
- prior selected snapshots for diversity.

Pros:

- can capture semantic progress,
- can prioritize states humans would consider promising,
- likely better for long-horizon tasks.

Cons:

- adds cost and latency,
- harder to evaluate independently,
- can overfit to persuasive agent narration,
- should not be the first implementation.

Use this after we have baseline data and an evaluation harness.

## Component Boundary

Keep the interface split:

- `SnapshotPolicy`: pure candidate decision.
- `SnapshotManager`: side effects, persistence, Daytona calls.
- `SnapshotSelector`: rank/select candidates for continuation.
- `ContinuationRunner`: restore/fork a selected snapshot and launch a new agent attempt.

This keeps Harbor, Daytona, and learned scoring replaceable.

## First Implementation Target

1. Parse `trajectory.json` into `SnapshotContext` objects.
2. Run both `EveryAgentStepPolicy` and `InterestingAgentStepPolicy` over a completed trial.
3. Persist candidate metadata next to the trial.
4. Add a Daytona-backed manager that can create a real restore reference at each selected candidate.
5. Add continuation runs from one selected restore reference.

## Daytona SDK Spike

Harbor's uv tool environment originally had `daytona==0.143.0`, and `AsyncSandbox` did not expose live sandbox snapshot/fork methods.

Upgrading Daytona inside Harbor's tool environment worked:

```bash
uv pip install --python /Users/danielgraviet/.local/share/uv/tools/harbor/bin/python --upgrade daytona
```

The upgraded environment has `daytona==0.194.0` and exposes:

```python
AsyncSandbox._experimental_create_snapshot(name: str, timeout: float | None = 60) -> None
AsyncSandbox._experimental_fork(name: str | None = None, timeout: float | None = 60) -> AsyncSandbox
```

After the upgrade, a Daytona oracle smoke run still passed:

```text
job_dir: jobs/daytona-oracle-smoke-sdk194
trials: 1/1
errors: 0
mean: 1.0
task: chess-best-move
reward: 1.0
```

This confirms the spike path is viable. The production path should pin Harbor and Daytona in a controlled environment instead of mutating the global Harbor tool env.
