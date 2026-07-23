# Phase 6 Failure Analysis

This document records observed behavior from the Phase 6 viability experiments and the current implementation. It is intentionally analytical. It does not propose fixes or preferred designs.

## 1. A snapshot can be valuable without being classified as valuable

The archive selector operates on stored metadata rather than directly inspecting the sandbox state. `archive_priority` ranks entries by heuristic priority and score in [go_explore/snapshots/selectors.py:67-79](/Users/danielgraviet/Desktop/projects/go-explore/go_explore/snapshots/selectors.py:67). The score is derived from event type, test counts, changed files, and terminal events in [go_explore/snapshots/policies.py:107-158](/Users/danielgraviet/Desktop/projects/go-explore/go_explore/snapshots/policies.py:107).

The `validated_progress` selector requires a `test_run` or `verifier` event, at least one passed test, and zero failed tests in [go_explore/snapshots/selectors.py:81-101](/Users/danielgraviet/Desktop/projects/go-explore/go_explore/snapshots/selectors.py:81). The `partial_progress` selector accepts partial test evidence or any `discovery` event in [go_explore/snapshots/selectors.py:103-121](/Users/danielgraviet/Desktop/projects/go-explore/go_explore/snapshots/selectors.py:103).

These selectors therefore depend on the event classifier and probe metadata being accurate. A persistent sandbox state can exist without satisfying the metadata conditions required for selection.

## 2. Search activity is usually not persistent sandbox progress

The snapshot policy only creates candidates for steps whose source is `agent` in [go_explore/snapshots/policies.py:47-50](/Users/danielgraviet/Desktop/projects/go-explore/go_explore/snapshots/policies.py:47). It assigns one event based on command and observation heuristics in [go_explore/snapshots/policies.py:57-85](/Users/danielgraviet/Desktop/projects/go-explore/go_explore/snapshots/policies.py:57).

For Git-related commands, `git reflog`, `git merge`, `git commit`, and `git branch` are explicitly classified as `command` events in [go_explore/snapshots/policies.py:76-78](/Users/danielgraviet/Desktop/projects/go-explore/go_explore/snapshots/policies.py:76). The investigative-command list used for `discovery` is separate in [go_explore/snapshots/policies.py:206-228](/Users/danielgraviet/Desktop/projects/go-explore/go_explore/snapshots/policies.py:206).

In the `git-leak-recovery` run, the trajectory contained `git log`, `git reflog`, `git show`, and `git grep`, but the archive contained only a zero-score `command` snapshot. The root solved, yet no child was selected. The command history represented useful agent knowledge, while the selected snapshot metadata did not represent it as reusable state.

## 3. File edits and setup state are represented differently

File-edit candidates record changed file paths in [go_explore/snapshots/policies.py:88-98](/Users/danielgraviet/Desktop/projects/go-explore/go_explore/snapshots/policies.py:88). The heuristic scorer gives file edits a fixed bonus in [go_explore/snapshots/policies.py:142-144](/Users/danielgraviet/Desktop/projects/go-explore/go_explore/snapshots/policies.py:142), but `partial_progress` does not select file-edit events in [go_explore/snapshots/selectors.py:103-112](/Users/danielgraviet/Desktop/projects/go-explore/go_explore/snapshots/selectors.py:103).

This creates a distinction between a state that contains persistent implementation work and a state that the selector considers eligible. The `kv-store-grpc` root produced file-edit snapshots for `/app/kv-store.proto` and `/app/server.py`, while its selected snapshot was classified as `test_run` and had no changed files.

## 4. The KV snapshot was selected because of a validation-probe false positive

The selected KV snapshot was `go-explore-kv-store-grpc__M2n4XCd-step-0`. Its archive entry recorded:

- event: `test_run`
- score: `4.0`
- tests passed: `1`
- tests failed: `null`
- changed files: none

The trajectory shows that step 0 was the `pip install grpcio==1.73.0 grpcio-tools==1.73.0` command. The observation contained `Successfully installed ...`. The former probe logic treated a generic success word as one passed test in [go_explore/snapshots/policies.py:241-265](/Users/danielgraviet/Desktop/projects/go-explore/go_explore/snapshots/policies.py:241).

The child restored that snapshot and solved the task. The state was plausibly useful because it preserved installed dependencies, but the recorded reason for eligibility was not an actual task test. The current source no longer treats generic `success` as test evidence; the historical archive still contains the earlier classification.

## 5. Root completion and archive completion are separate states

Branch continuation first checks for a root `result.json`, then separately checks for `archive.json` in [go_explore/experiment_runner.py:360-389](/Users/danielgraviet/Desktop/projects/go-explore/go_explore/experiment_runner.py:360). A root directory can therefore exist with a result file while lacking the archive required for continuation.

This occurred for the initial `kv-store-grpc` launch. Harbor failed while importing `go_explore.agents.factory`, leaving a pending result directory without an archive. The continuation phase reported `skipped_missing_archive`, even though the root directory existed.

## 6. Existing-job skipping can preserve an old failure

Continuation records are marked `skipped_existing` when a result file already exists unless rerun mode is enabled in [go_explore/experiment_runner.py:449-470](/Users/danielgraviet/Desktop/projects/go-explore/go_explore/experiment_runner.py:449). This means a failed or incomplete root directory can be treated as an existing completed artifact by a later invocation. The subsequent branch phase then observes the old directory state, including a missing archive.

The resulting output can contain both `skipped_existing` for the root and `skipped_missing_archive` for the branch phase. These statuses describe different checks on the same job directory.

## 7. The Harbor import path crosses a process boundary

The launcher starts Harbor as a subprocess. The local agent import path is passed in the Harbor command in [go_explore/harbor.py:24-48](/Users/danielgraviet/Desktop/projects/go-explore/go_explore/harbor.py:24). Harbor then imports the agent in its own Python process.

The earlier `uv run` failure was `No module named 'go_explore'` inside Harbor, not inside the top-level Go Explore process. The current subprocess environment helper prepends the repository path in [go_explore/harbor.py:97-105](/Users/danielgraviet/Desktop/projects/go-explore/go_explore/harbor.py:97), and continuation launches use the same environment path in [go_explore/continuations.py:707-713](/Users/danielgraviet/Desktop/projects/go-explore/go_explore/continuations.py:707).

The failure was therefore an execution-environment mismatch between the launcher process and Harbor's agent-import process.

## 8. Planned budgets are not execution limits

Fixed-budget plans describe token allocations, but the plan contract labels enforcement as `planning_only` in [go_explore/fixed_budget.py:10-18](/Users/danielgraviet/Desktop/projects/go-explore/go_explore/fixed_budget.py:10). Actual Harbor jobs can exceed the planned allocation.

The Phase 6 build-cython retry arm illustrates this distinction: the analysis recorded approximately 9.16 million tokens and `$0.87` despite a smaller planned budget. The budget field in analysis identifies an allocation, not a stopping condition.

## 9. Missing child rows do not necessarily mean child failures

The runner creates a planned continuation record for each configured child slot, then only makes plans for snapshots returned by the selector in [go_explore/experiment_runner.py:405-447](/Users/danielgraviet/Desktop/projects/go-explore/go_explore/experiment_runner.py:405). If fewer eligible snapshots exist than configured slots, some planned children have no result directory.

The successful KV run had four analysis rows: one root, one successful child, and two missing child results. The task summary nevertheless reported the experiment as solved with one fork in `docs/experiments/main-benchmark/analysis/e2e-partial-progress-kv-store-grpc/task-summary.csv:2`.

This combines outcome data from executed jobs with planned-but-unexecuted child slots. The warnings file records those missing result directories separately from task reward.

## 10. The observed task results are highly task-dependent

The Phase 6 pilot showed different behaviors across tasks. `fix-git` branches solved, `regex-log` branch children failed, and build-cython continuation arms were affected by infrastructure failures. These results are recorded in `docs/experiments/viability/phase6-viability-pilot/analysis/task-summary.csv:2-10`.

The KV run differs from the earlier failures: the root solved, one child restored a partial/setup state and solved, and no clean retry comparison was included. Its `unique_success_beyond_baselines` field is therefore an analysis label for that run shape, not evidence from a matched retry control within the same experiment.

## 11. Shutdown errors are distinct from task errors

The recurring `asyncio.exceptions.CancelledError` appears in Harbor's Daytona cleanup callback after job completion. The stack terminates in the WebSocket reader used by the Daytona client. In completed jobs, this appears after Harbor has written `result.json` and reported trial results.

The cleanup traceback is therefore separate from the task reward, agent exception, and continuation result. Incomplete jobs require the job result and execution status to distinguish a cleanup-time cancellation from a failure during task execution.
