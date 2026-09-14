# Checkpoint Handoff Diagnostic

`checkpoint-diagnostic` is a mechanism study, not a fixed-total-budget
benchmark. It compares a shared root checkpoint with a restored new agent and
a clean new agent at the same remaining token cap. The root's original agent
is reported only as an observed post-checkpoint delta: v1 cannot pause it at
an exact cap while preserving its in-memory context.

Run a canary after the root job has finished and its archive contains a chosen
snapshot:

```bash
uv run python -m go_explore.cli checkpoint-diagnostic \
  jobs/<root-job> \
  --snapshot-name <exact-daytona-snapshot-name> \
  --remaining-token-budget 200000 \
  --child-job-name <root-job>-diagnostic-child \
  --clean-job-name <root-job>-diagnostic-clean \
  --context-mode preflight_verification \
  --execute
```

Without `--execute`, the command validates the checkpoint and writes a planned
report at `jobs/<root-job>/checkpoint-diagnostic.json`. With `--execute`, it
launches the restored child and clean retry sequentially. Both inherit the
root task, model, timeout-related agent settings, and exactly the requested
`token_budget`; the child alone receives the exact Daytona snapshot.

Inspect the report before treating a result as evidence:

- `diagnostic_only` must be `true`.
- `checkpoint_tokens` and `checkpoint_elapsed_seconds` show the separately
  accounted root prefix.
- `restored_child` must name the selected snapshot's child job and have
  `start_state_type: full_snapshot`; `clean_retry` must have
  `start_state_type: clean`.
- Both new-agent arms must have the same `planned_token_cap`.
- A root arm with `status: unavailable` is not cap-comparable and any outcome
  involving it remains inconclusive.

Use this result memo template:

```text
Diagnostic only: <root job / checkpoint / seed>
Root prefix: <tokens>, <seconds>; checkpoint verifier: <result or unavailable>
Remaining cap R: <tokens>
Root continuation: <reward, post-checkpoint tokens/time, availability>
Restored child: <reward, tokens/time, restore overhead, verifier result>
Clean retry: <reward, tokens/time, verifier result>
Outcome: <report outcome>
Interpretation: <strictly observed mechanism finding or inconclusive>
```

Do not combine these rows with headline solve-rate tables. The shared prefix
plus three post-checkpoint arms intentionally uses more total compute than a
normal retry or branch experiment.
