# Failure Case Audit

## Summary

This audit covers the available Phase 4 smoke artifacts plus the Phase 5 context-ablation smoke. The strongest negative result is `regex-log`: scratch retry sometimes solved the task, but all restored snapshot continuations failed.

The failures do not show that snapshot continuation is unusable. They show that the current implementation can preserve and amplify bad intermediate state. The most common pattern is a child restoring a snapshot around an unverified `/app/regex.txt` or local test file, then confidently marking the task complete even though the hidden verifier returns reward `0`.

Primary artifacts:

- `docs/experiments/main-benchmark/analysis/smoke/regex-log-r3/run-summary.csv`
- `docs/experiments/main-benchmark/analysis/smoke/regex-log-r3/task-summary.csv`
- `docs/experiments/main-benchmark/analysis/smoke/regex-log-r3/warnings.json`
- `docs/experiments/main-benchmark/analysis/smoke/fix-git/run-summary.csv`
- `docs/experiments/main-benchmark/analysis/smoke/context-ablation-regex-log-20260722/run-summary.csv`
- `docs/experiments/context-ablation-smoke-20260722.md`

## Headline Contrast

`regex-log-r3` is the main failure case because clean retry solved 2/5 attempts, while both branch methods solved 0/3 rows. Each branch method ran one root plus two continuations, and all continuation rows failed.

| Method | Runs | Solved | Notes |
| --- | ---: | ---: | --- |
| `retry` | 5 | 2 | Clean restarts can find the solution. |
| `random_branch` | 3 | 0 | Root timed out; both continuations failed. |
| `promising_branch` | 3 | 0 | Root failed; both archive-priority continuations failed. |

`fix-git` is the positive control. Its branch roots and continuations succeeded, so the snapshot path can work when the task and selected states are forgiving.

## Concrete Examples

| Case | Category | Run ID | Snapshot | Selector | Outcome |
| --- | --- | --- | --- | --- | --- |
| 1 | Context misuse plus wrong-state anchoring | `phase4-smoke-regex-log-r3-promising-branch-seed-0-cont-0` | `go-explore-regex-log__ZnUYp6i-step-0` | `archive_priority`, score `1.25`, cell `{/app/regex.txt}` | Reward `0.0`, verifier expected 9 dates but got 10 wrong/extra matches. |
| 2 | Bad selector choice | `phase4-smoke-regex-log-r3-promising-branch-seed-0-cont-1` | `go-explore-regex-log__ZnUYp6i-step-7` | `archive_priority`, score `1.25`, cell `{/tmp/test.py}` | Reward `0.0`, verifier got tuples from capturing groups instead of full date strings. |
| 3 | Bad selector choice plus weak local tests | `phase4-smoke-regex-log-r3-random-branch-seed-0-cont-0` | `go-explore-regex-log__y4NVaLf-step-11` | `random`, score `1.25`, cell `{/tmp/test_findall.pl}` | Reward `0.0`, verifier found only 5 expected dates. |
| 4 | State-fidelity failure | `phase4-smoke-regex-log-r3-random-branch-seed-0-cont-1` | `go-explore-regex-log__y4NVaLf-step-0` | `random`, score `1.25`, cell `{/app/regex.txt}` | Reward `0.0`, verifier missed `2016-12-31` because the restored regex constrained days too tightly. |
| 5 | Snapshot/agent runtime failure | `phase4-smoke-regex-log-r3-random-branch-seed-0-root` | Root produced snapshots, then timed out | `random` root archive | Outcome `agent_error`, exception `AgentTimeoutError`, reward `0.0`. |
| 6 | Context ablation negative result | `phase5-context-ablation-regex-log-20260722-none-snapshot-0` | `go-explore-regex-log__VgDNmsH-step-0` | `explicit`, cell unavailable in joined row; archive entry is `{/app/regex.txt}` | Reward `0.0`; removing parent context cut tokens to `5254` but still failed. |

## Failure Categories

### State-Fidelity Failures

Full snapshots faithfully restore task files, including incorrect partial solutions. In `regex-log`, restoring `/app/regex.txt` often preserved an already-bad regex. The child then edited or reasoned around that inherited artifact instead of re-deriving the task from scratch.

Evidence:

- `go-explore-regex-log__ZnUYp6i-step-0` restored an `/app/regex.txt` edit and failed.
- `go-explore-regex-log__y4NVaLf-step-0` restored an `/app/regex.txt` edit and failed.
- `go-explore-regex-log__VgDNmsH-step-0` restored an `/app/regex.txt` edit and failed across all three context modes in the ablation smoke.

Implementation fixes:

- Add probe scoring that executes task-relevant checks before prioritizing a snapshot.
- Penalize snapshots that modify final-answer files without any successful or high-signal validation.
- Record final-answer file diffs in the archive so selectors can treat them differently from setup-only state.

Research limitation:

Snapshot reuse is not equivalent to reusable progress. Some restored state is actively misleading.

### Context-Misuse Failures

The `parent_summary` mode can make a failed parent attempt sound useful. In `phase4-smoke-regex-log-r3-promising-branch-seed-0-cont-0`, the child received a summary of the parent edit, tested narrow examples, declared success, and marked the task complete. The verifier then returned reward `0`.

The Phase 5 ablation suggests inherited context is not the only problem: `context_mode=none` also failed from `go-explore-regex-log__VgDNmsH-step-0`. However, context clearly affects cost. The `none` continuation used `5254` tokens, while `parent_summary` used `127274` tokens and `critical_parent_summary` used `109298` tokens.

Implementation fixes:

- Keep `context_mode=none` and `critical_parent_summary` as first-class benchmark arms.
- Make failed-parent summaries explicitly skeptical: state that the parent did not solve the task and that inherited files may be wrong.
- Prefer child prompts that ask for independent validation before editing inherited final-answer files.

Research limitation:

Context ablation can reduce cost without improving correctness. The paper should not claim that prompt context removal solves bad continuation outcomes.

### Bad Selector Choices

Archive scoring currently treats several generic events as promising. The selected `regex-log-r3` snapshots included:

- `{/app/regex.txt}` with score `1.25`
- `{/tmp/test.py}` with score `1.25`
- `{/tmp/test_findall.pl}` with score `1.25`

None had a reward signal. One selected local test snapshot led to a regex that passed the agent's hand-written checks but returned tuples under Python `re.findall`, failing the hidden verifier.

Implementation fixes:

- Score verifier-like probes above file edits.
- Treat local scratch-test files as weak evidence unless they are tied to a passing command.
- Track whether a command exercised the exact runtime semantics from the task description, such as Python `re.findall` rather than Perl regex behavior.

Research limitation:

The current selector is a heuristic selector, not evidence that a state is actually closer to solving the task.

### Snapshot/Restore Failures

No analyzed continuation failed because Daytona could not restore the requested snapshot. Restored jobs show `start_state_type=full_snapshot` and task execution reached the verifier.

The remaining snapshot infrastructure gaps are measurement gaps:

- `restore_overhead_seconds` is still `unknown` in the analyzed rows.
- Some continuation rows lack joined `snapshot_cell_key` metadata even when the source archive has it.
- `repeated_setup_score` is unknown in these smoke outputs.

Implementation fixes:

- Keep recording exact snapshot creation latency.
- Add exact restore latency to continuation reports and analysis tables.
- Improve lineage joins so explicit continuation snapshots carry their archive cell metadata.

Research limitation:

Current tables can compare solve rates and token/cost totals, but cannot yet make precise claims about restore latency savings.

### Model Failures

Several failures are model-level task-solving failures independent of snapshot infrastructure. For `regex-log`, failed agents repeatedly believed local tests were sufficient while hidden verifier cases exposed:

- incorrect "last date" behavior,
- Python `re.findall` tuple output due to multiple capturing groups,
- invalid day/month handling,
- IPv4 boundary or leading-zero mistakes.

Implementation fixes:

- Add task-specific probe templates for common benchmark patterns.
- Ask the agent to run checks in the exact language/runtime specified by the task.

Research limitation:

A branch can only help if the child model can correctly evaluate and revise the inherited work. Snapshotting cannot compensate for shallow validation.

### Benchmark Or Verifier Issues

The `regex-log` verifier appears useful rather than suspect: it exposes realistic hidden cases and uses the exact `re.findall(pattern, log_text, re.MULTILINE)` behavior described in the task. The observed failures are valid task failures.

The main benchmark-process issue is that some analysis rows remain incomplete or planning-only:

- Budget fields are `planning_only`, not enforced caps.
- `fix-git` retry rows are `missing_result` because that smoke did not execute the planned retry attempts.
- The current failure audit is based on smoke data, not a full paper benchmark.

Implementation fixes:

- Keep planning-only labels visible in tables and memos.
- Exclude `missing_result` rows from solve-rate claims unless explicitly discussing planned-but-unrun jobs.

Research limitation:

These artifacts support directional engineering decisions. They should not be presented as final benchmark evidence.

## Chess-Style Rubber-Stamping

The ticket asked to cover the chess-style rubber-stamping failure if reproduced. The current checked artifacts do not include a reproduced chess failure. The closest reproduced pattern is in `regex-log`: children accepted inherited or self-written local tests as sufficient, declared the task complete, and were contradicted by the hidden verifier.

## Takeaways

The next engineering work should prioritize selector and validation quality over adding more continuation attempts. In these failures, continuations generally ran successfully and reached the verifier; the issue was that the restored states and context were not actually reliable progress.

Supported claims:

- Restored continuation can fail even when clean retry sometimes succeeds.
- Parent context can be expensive.
- Generic file-edit snapshots are weak evidence of useful progress.
- Hidden verifier failures are often caused by inadequate local validation.

Weakened claims:

- "Snapshot restore saves tokens" is not consistently supported for parent-summary continuations.
- "Removing parent context fixes branch failures" is not supported by the context-ablation smoke.

Refuted for current smoke data:

- The current archive-priority selector reliably identifies promising `regex-log` continuation states.
