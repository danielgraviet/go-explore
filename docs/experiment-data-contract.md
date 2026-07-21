# Experiment Data Contract

This contract defines the minimum artifacts needed to evaluate the claims in
`docs/essay.md`. It is intentionally practical: Phase 2 tickets should make
these fields available without redesigning Harbor, Daytona, or the snapshot
archive.

## Artifact Set

A fixed-budget experiment should produce three normalized artifacts in addition
to the raw Harbor job directories:

| Artifact | Shape | Purpose |
| --- | --- | --- |
| `task-summary.csv` | one row per `(experiment_id, task_id, method)` | headline task-level comparison |
| `run-summary.csv` | one row per root, scratch, or continuation run | budget, lineage, and outcome accounting |
| `events.jsonl` | append-only event records | mechanistic analysis of commands, snapshots, tests, and repeated work |

Raw job artifacts remain authoritative. The normalized files should store
references back to `jobs/<job>/...` paths so claims can be audited.

## Missing Values

Use these conventions consistently:

| Case | Representation |
| --- | --- |
| Field is not applicable | `null` |
| Field should exist but source artifact is missing | `"missing"` in a paired status/reason field |
| Field may exist but current extractor cannot read it | `"unknown"` in a paired status/reason field |
| Numeric metric is unavailable | `null`, never `0` |
| Failed run with no trial result | `reward = null`, `outcome = "infra_error"` or `outcome = "missing_result"` |

Examples:

```json
{
  "total_tokens": null,
  "total_tokens_status": "unknown",
  "total_tokens_reason": "provider metrics absent from trial result"
}
```

Do not silently impute costs, tokens, or timings.

## Task-Level Summary

`task-summary.csv` answers: under a fixed budget, which method solved which
tasks?

| Field | Required | Status Today | Source / Follow-Up |
| --- | --- | --- | --- |
| `experiment_id` | yes | missing | P3 planner should assign this. |
| `task_id` | yes | exists | Trial `result.json.task_name` or `task_id.path`. |
| `difficulty` | no | partial | Task metadata via Harbor/task cache, not current result summary. |
| `category` | no | partial | Task metadata via Harbor/task cache, not current result summary. |
| `method` | yes | missing | P3 planner: `single`, `retry`, `best_of_n`, `random_branch`, `promising_branch`, `oracle_branch`. |
| `model_class` | yes | partial | Current artifacts store exact model; experiment config should map to class. |
| `solved` | yes | exists | Any included run has reward `1.0` and no exception. |
| `n_runs` | yes | partial | Count run-summary rows for same task/method. |
| `n_attempts` | yes | partial | Harbor `n_attempts` plus continuation count. |
| `n_snapshots_created` | yes | partial | Archive has selected cells; P2-T003 should log every creation. |
| `n_snapshots_forked` | yes | partial | Continuation report has attempts; P2-T003 should log selections. |
| `total_tokens` | yes | partial | Trial `agent_result` has provider metrics when available. |
| `total_cost_usd` | yes | partial | Trial `agent_result.cost_usd` when available. |
| `wall_clock_seconds` | yes | partial | Job/trial started/finished timestamps. |
| `snapshot_overhead_seconds` | yes | partial | `SnapshotTiming.backend_seconds`; not persisted today. |
| `restore_overhead_seconds` | no | missing | Needs Daytona/Harbor timing instrumentation. |
| `unique_success_beyond_baselines` | no | missing | Derived by analysis tables. |

Example:

```csv
experiment_id,task_id,difficulty,category,method,model_class,solved,n_runs,n_attempts,n_snapshots_created,n_snapshots_forked,total_tokens,total_cost_usd,wall_clock_seconds,snapshot_overhead_seconds,restore_overhead_seconds,unique_success_beyond_baselines
phase4-main-001,fix-git,medium,software-engineering,promising_branch,strong_closed,true,2,2,4,1,38122,0.0612,118.4,14.8,,false
```

## Run-Level Summary

`run-summary.csv` answers: what happened in each root, scratch, or continuation
run, and where did it come from?

| Field | Required | Status Today | Source / Follow-Up |
| --- | --- | --- | --- |
| `experiment_id` | yes | missing | P3 planner. |
| `run_id` | yes | partial | Harbor trial `id`; planner should assign stable IDs before execution. |
| `job_dir` | yes | exists | Harbor job path. |
| `trial_name` | yes | exists | Trial `result.json.trial_name`. |
| `task_id` | yes | exists | Trial `result.json.task_name` or `task_id.path`. |
| `method` | yes | missing | P3 planner. |
| `start_state_type` | yes | missing | P3-T002: `clean`, `diff_only`, `diff_transcript`, `command_replay`, `full_snapshot`. |
| `parent_run_id` | no | partial | Continuation report has parent trial; needs stable run ID mapping. |
| `parent_job_dir` | no | exists for continuations | `continuation-report.json`. |
| `parent_trial_name` | no | exists for continuations | `continuation-report.json`. |
| `parent_snapshot` | no | exists for continuations | `ContinuationAttempt.snapshot_name`. |
| `snapshot_cell_key` | no | partial | `archive.json` entries when archive exists. |
| `selector_mode` | no | missing | P3-T001. |
| `selector_score` | no | partial | `ArchiveEntry.score`. |
| `selector_reasons` | no | missing | Current score reasons are not persisted. |
| `reward` | yes | exists | Trial verifier reward. |
| `outcome` | yes | partial | Derived: `success`, `fail`, `agent_error`, `infra_error`, `missing_result`. |
| `exception_type` | no | exists | Trial exception info or continuation report. |
| `n_input_tokens` | no | exists when provider reports | Trial `agent_result.n_input_tokens`. |
| `n_output_tokens` | no | exists when provider reports | Trial `agent_result.n_output_tokens`. |
| `n_cache_tokens` | no | exists when provider reports | Trial `agent_result.n_cache_tokens`. |
| `total_tokens` | yes | partial | Derived when token fields exist. |
| `cost_usd` | yes | partial | Trial `agent_result.cost_usd`. |
| `duration_seconds` | yes | partial | Trial `started_at`/`finished_at`. |
| `agent_execution_seconds` | no | exists when Harbor records | Trial `agent_execution.started_at`/`finished_at`. |
| `environment_setup_seconds` | no | exists when Harbor records | Trial `environment_setup.started_at`/`finished_at`. |
| `snapshot_overhead_seconds` | no | missing | Persist `SnapshotTiming.backend_seconds`. |
| `restore_overhead_seconds` | no | missing | Needs continuation environment timing. |
| `repeated_setup_score` | no | missing | P3-T004. |
| `failure_mode` | no | missing | P4-T004 audit or later classifier. |

Example:

```csv
experiment_id,run_id,job_dir,trial_name,task_id,method,start_state_type,parent_run_id,parent_job_dir,parent_trial_name,parent_snapshot,reward,outcome,n_input_tokens,n_output_tokens,total_tokens,cost_usd,duration_seconds,repeated_setup_score
phase4-main-001,run-fix-git-root,jobs/phase4-fix-git-root,fix-git__abc123,fix-git,promising_branch,clean,,,,,0.0,fail,17295,1814,19109,0.02757625,54.0,
phase4-main-001,run-fix-git-cont-0,jobs/phase4-fix-git-cont-0,fix-git__def456,fix-git,promising_branch,full_snapshot,run-fix-git-root,jobs/phase4-fix-git-root,fix-git__abc123,go-explore-fix-git__abc123-step-6,1.0,success,12000,900,12900,0.019,42.2,0.15
```

## Event-Level Log

`events.jsonl` is the append-only mechanistic trace. Each event must include
common fields plus event-specific fields.

### Common Fields

| Field | Required | Notes |
| --- | --- | --- |
| `schema_version` | yes | Start with `"go-explore-event-v1"`. |
| `event_type` | yes | One of the event types below. |
| `event_id` | yes | Stable ID or deterministic hash if available. |
| `experiment_id` | yes | Assigned by planner. |
| `run_id` | yes | Stable root/scratch/continuation run ID. |
| `job_dir` | yes | Raw Harbor job path. |
| `trial_name` | no | Null for pre-trial planning events. |
| `task_id` | no | Known once task is selected. |
| `step_id` | no | ATIF/snapshot step when available. |
| `timestamp` | no | Use source timestamp if available. |

### Event Types

| Event | Status Today | Required Event-Specific Fields |
| --- | --- | --- |
| `command_executed` | partial | `command`, `duration_seconds`, `exit_status`, `output_hash`, `source`. |
| `file_changed` | partial | `path`, `change_type`, `diff_hash`, `detected_by`. |
| `test_run` | partial | `command`, `framework`, `tests_passed`, `tests_failed`, `output_hash`. |
| `dependency_installed` | missing | `manager`, `package`, `version`, `command`. |
| `snapshot_created` | partial | `snapshot_name`, `cell_key`, `score`, `selector_reasons`, `backend`, `overhead_seconds`. |
| `snapshot_selected` | partial | `snapshot_name`, `cell_key`, `priority`, `score`, `times_selected`, `selector_mode`, `selector_reasons`. |
| `continuation_started` | partial | `child_run_id`, `child_job_dir`, `parent_run_id`, `parent_snapshot`, `start_state_type`, `context_mode`. |
| `verifier_result` | exists | `reward`, `output_hash`, `exception_type`. |

Examples:

```jsonl
{"schema_version":"go-explore-event-v1","event_type":"command_executed","event_id":"run-fix-git-root:step-2:cmd-0","experiment_id":"phase4-main-001","run_id":"run-fix-git-root","job_dir":"jobs/phase4-fix-git-root","trial_name":"fix-git__abc123","task_id":"fix-git","step_id":2,"timestamp":"2026-07-06T16:01:58.976376Z","command":"git status\n","duration_seconds":0.5,"exit_status":null,"output_hash":"sha256:...","source":"atif_trajectory"}
{"schema_version":"go-explore-event-v1","event_type":"snapshot_created","event_id":"run-fix-git-root:snapshot:go-explore-fix-git__abc123-step-6","experiment_id":"phase4-main-001","run_id":"run-fix-git-root","job_dir":"jobs/phase4-fix-git-root","trial_name":"fix-git__abc123","task_id":"fix-git","step_id":6,"snapshot_name":"go-explore-fix-git__abc123-step-6","cell_key":"<test_run>","score":3.0,"selector_reasons":["has validation signal"],"backend":"daytona","overhead_seconds":4.8}
{"schema_version":"go-explore-event-v1","event_type":"continuation_started","event_id":"run-fix-git-cont-0:start","experiment_id":"phase4-main-001","run_id":"run-fix-git-root","job_dir":"jobs/phase4-fix-git-root","trial_name":"fix-git__abc123","task_id":"fix-git","child_run_id":"run-fix-git-cont-0","child_job_dir":"jobs/phase4-fix-git-cont-0","parent_run_id":"run-fix-git-root","parent_snapshot":"go-explore-fix-git__abc123-step-6","start_state_type":"full_snapshot","context_mode":"parent_summary"}
{"schema_version":"go-explore-event-v1","event_type":"verifier_result","event_id":"run-fix-git-cont-0:verifier","experiment_id":"phase4-main-001","run_id":"run-fix-git-cont-0","job_dir":"jobs/phase4-fix-git-cont-0","trial_name":"fix-git__def456","task_id":"fix-git","reward":1.0,"output_hash":"sha256:...","exception_type":null}
```

## Current Artifact Mapping

| Current Artifact | Useful Fields | Gaps |
| --- | --- | --- |
| `jobs/<job>/config.json` | job name, dataset, task filter, agent, model, environment, Harbor settings | no experiment method, seed, or budget allocation |
| `jobs/<job>/result.json` | job ID, start/finish time, total trials, error count, aggregate mean | no per-run token/cost details |
| `jobs/<job>/<trial>/result.json` | trial ID/name, task, source, reward, exceptions, tokens, cost, setup/execution/verifier timings | no parent lineage, snapshot metadata, repeated-work metrics |
| `jobs/<job>/<trial>/agent/trajectory.json` | ATIF steps, messages, commands, observations, per-step metrics | command exit status and changed files are partial/heuristic |
| `jobs/<root>/continuation-report.json` | root job/trial/reward, continuation job, parent snapshot, branch reward, success | no selector mode/reasons, budget fields, stable run IDs |
| `jobs/<job>/archive.json` | snapshot name, cell key, score, event, changed files, selection count, depth | not present in older local jobs; creation events and score reasons are not persisted |
| `SnapshotTiming` in memory | policy/backend/store/total seconds, candidate counts | not persisted today |

## Validation Notes

This contract was validated against current code and local Harbor artifacts:

- `go_explore.results.summarize_job()` reads job/trial rewards and exceptions.
- `go_explore.continuations.ContinuationReport` records parent snapshot lineage for continuation jobs.
- `go_explore.snapshots.archive.SnapshotArchive` stores cell-level snapshot metadata when `archive.json` exists.
- Local `jobs/daytona-fix-git-haiku45-terminus2/` includes provider token/cost fields, trial timings, verifier reward, and ATIF trajectory commands.
- Local continuation reports such as `jobs/context-check-root/continuation-report.json` include parent snapshot lineage but not selector, budget, or event-level fields.

No live benchmark was run for this ticket.

## Follow-Up Tickets

- P2-T003 should implement `snapshot_created`, `snapshot_selected`, and `continuation_started` JSONL events.
- P2-T004 should normalize budget fields in reports and summaries.
- P2-T005 should implement structured command, test, dependency, and changed-file extraction.
- P3-T004 should compute repeated-work metrics from event logs.
- P3-T006 should generate `task-summary.csv` and `run-summary.csv` from raw artifacts.
