# Commands

Short operator reference for running Go-Explore experiments in this repo.

## Setup

```bash
set -a; source .env; set +a
export PATH="$HOME/.local/bin:$PATH"
export PYTHONPATH="$PWD"
```

Use the checked-in virtualenv when possible:

```bash
.venv/bin/python -m pytest -q
```

## tmux

Use the existing session when one is already running:

```bash
tmux list-sessions
tmux list-windows -t GoExplore-0 -F '#{window_index} #{window_name} #{window_active} #{pane_current_command}'
tmux capture-pane -t GoExplore-0:<window-name> -p -S -80
```

Launch a new window in that session:

```bash
tmux new-window -t GoExplore-0 -n <window-name> -c /Users/danielgraviet/Desktop/projects/go-explore
tmux send-keys -t GoExplore-0:<window-name> '<command>' Enter
```

## Run Experiments

Preferred entry point for fixed-budget benchmark runs:

```bash
.venv/bin/python -m go_explore.cli run-experiment \
  --dataset terminal-bench@2.0 \
  --task-name <task-name> \
  --experiment-id <experiment-id> \
  --job-prefix <job-prefix> \
  --model anthropic/claude-haiku-4-5-20251001 \
  --total-token-budget 100000 \
  --method single \
  --method retry \
  --method random_branch \
  --method promising_branch \
  --seed 0 \
  --n-retries 5 \
  --n-branch-continuations 2 \
  --branch-context-mode preflight_verification \
  --manifest-path docs/experiments/main-benchmark/manifests/primary/<task-name>.json \
  --analysis-dir docs/experiments/main-benchmark/analysis/<experiment-id> \
  --execute
```

Use `--branch-context-mode none` for viability work when the point is to test
the restored sandbox without extra parent narrative.

For smoke runs, point at `docs/experiments/main-benchmark/manifests/smoke/<task>.json`
and `docs/experiments/main-benchmark/analysis/smoke/<task>/`.

## Continuations

If a root has already finished, run continuations from its archive:

```bash
.venv/bin/python -m go_explore.cli continue-from-snapshots \
  jobs/<root-job-dir> \
  --from-archive \
  --selector-mode archive_priority \
  --max-snapshots 2 \
  --job-prefix <continuation-prefix> \
  --execute
```

Use `--selector-mode random` with `--selector-seed 0` for the random-branch
control.

## Start-State Baselines (`clean` / `diff_only` / `full_snapshot`)

`plan-start-state-baselines` plans (but does not execute) child jobs that
start a task from different states, to isolate how much benefit comes from
restored environment state vs. restored code vs. nothing:

- `clean` — fresh task environment, no parent state.
- `diff_only` — fresh task environment + the parent's `git diff` applied via
  `git apply` before the agent's first turn. Filesystem operation, not
  context injection: with `context_mode=original_task_only` the diff text is
  never shown to the agent and costs zero prompt tokens. Implemented in
  `go_explore/snapshots/diff_only.py`, wired through
  `SnapshotAwareAgent.setup()` in `go_explore/agents/snapshot_agent.py`.
- `full_snapshot` — restores a full Daytona sandbox snapshot.

```bash
# 1. Plan: point at a parent job dir + diff file, ask for diff_only
.venv/bin/python -m go_explore.cli plan-start-state-baselines jobs/<root-job-dir> \
  --start-state-type diff_only \
  --diff-path jobs/<root-job-dir>/parent.diff \
  --job-prefix <experiment-prefix> \
  --model anthropic/claude-haiku-4-5-20251001 \
  --manifest-path jobs/<root-job-dir>/start-state-plan.json

# prints: diff_only  original_task_only  ready  <experiment-prefix>-diff-only
# harbor run ... --ak context_mode=original_task_only --ak diff_path=jobs/<root-job-dir>/parent.diff

# 2. Run: execute the printed command directly (no --execute flag on this subcommand)
harbor run --agent-import-path go_explore.agents.factory:SnapshotAwareTerminus2 \
  --env daytona --jobs-dir jobs --n-attempts 1 --n-concurrent 1 \
  --dataset terminal-bench@2.0 --model anthropic/claude-haiku-4-5-20251001 \
  --include-task-name <task-name> --n-tasks 1 \
  --job-name <experiment-prefix>-diff-only --export-traces \
  --ak context_mode=original_task_only \
  --ak diff_path=jobs/<root-job-dir>/parent.diff
```

If `git apply` fails, `SnapshotAwareAgent` raises `DiffApplyFailed` before
the agent runs, so a bad diff shows up as an executor failure
(`exception_type="DiffApplyFailed"`), not a task failure. `executor_status`
on the plan is `"ready"` only if the diff file exists on disk at plan time,
else `"pending_parent_diff"` (mirrors `full_snapshot`'s
`"pending_root_archive"`) — `experiment_runner.py` skips anything not
`"ready"`.

**Gotcha:** `git apply` runs with `cwd=environment.task_env_config.workdir`,
which is not always the git repo root (e.g. for `fix-git`, `workdir` is
already `/app/personal-site`, the repo root itself). Diffs should come from
an actual `git diff` run inside the parent's own checkout so paths are
anchored correctly by construction — don't hand-write synthetic diffs
without checking where the task's repo actually lives.

Tests: `tests/test_diff_only.py` (apply mechanics), `tests/test_snapshot_agent.py`
(`test_diff_only_applies_to_filesystem_not_agent_context`,
`test_diff_only_apply_failure_blocks_agent_run`,
`test_snapshot_aware_terminus2_accepts_diff_path_without_wrapped_leak`),
`tests/test_continuations.py` / `tests/test_cli.py` (plan-level
`executor_status` and command-shape checks). Full ticket:
`tasks/phase-6-fixes/T007-create-start-states.md`.

### `diff_only + transcript` (compressed-memory comparator)

`--diff-only-context-mode full_transcript_summary` adds a fourth arm: the
same filesystem-applied diff as `diff_only`, plus a deterministic,
rule-based text summary of the parent's trajectory (commands run, files
touched, observed test pass/fail counts, last verifier output) injected into
the child's prompt. No model call — see `go_explore/snapshots/transcript.py`.
This isolates "does text memory on top of code state help" from
`full_snapshot`'s "does the whole restored sandbox help."

```bash
.venv/bin/python -m go_explore.cli plan-start-state-baselines jobs/<root-job-dir> \
  --start-state-type diff_only \
  --diff-path jobs/<root-job-dir>/parent.diff \
  --diff-only-context-mode full_transcript_summary \
  --job-prefix <experiment-prefix> \
  --model anthropic/claude-haiku-4-5-20251001 \
  --manifest-path jobs/<root-job-dir>/start-state-plan.json

# prints: diff_only  full_transcript_summary  ready  <experiment-prefix>-diff-only-transcript
# harbor run ... --ak context_mode=full_transcript_summary \
#   --ak diff_path=jobs/<root-job-dir>/parent.diff \
#   --ak parent_context_path=jobs/<root-job-dir>/<parent-trial>/agent/transcript-summary.md
```

The job name auto-suffixes to `-diff-only-transcript` (vs plain `diff_only`'s
`-diff-only`) so both arms can be planned from the same root without
colliding. The transcript file is written to
`jobs/<root-job-dir>/<parent-trial>/agent/transcript-summary.md` at plan
time — inspect it directly before running a batch.

Tests: `tests/test_transcript.py` (summary generation: commands, files, test
runs, dependency installs, last observation, truncation, determinism,
prompt-contract discipline), `tests/test_continuations.py`
(`write_transcript_summary_context`, `plan_start_state_baselines` wiring),
`tests/test_snapshot_agent.py`
(`test_snapshot_aware_agent_full_transcript_summary_uses_disclaimer_prompt`).
Full ticket: `tasks/phase-6-fixes/T008-diff-transcript.md`.

### `diff_only + command_log` (exact-memory comparator)

`--diff-only-context-mode command_log` adds a fifth arm: the same
filesystem-applied diff, plus a deterministic, ordered command+output log
(literal commands and their observed terminal excerpts, grouped by ATIF
step) injected into the child's prompt. No model call, no replay execution —
see `go_explore/snapshots/command_log.py`. Distinct in shape from
`full_transcript_summary`'s categorized narrative: this is the most explicit
compressed-memory condition short of actually replaying the commands, and
tests exact execution memory against summary memory and against
`full_snapshot`.

```bash
.venv/bin/python -m go_explore.cli plan-start-state-baselines jobs/<root-job-dir> \
  --start-state-type diff_only \
  --diff-path jobs/<root-job-dir>/parent.diff \
  --diff-only-context-mode command_log \
  --job-prefix <experiment-prefix> \
  --model anthropic/claude-haiku-4-5-20251001 \
  --manifest-path jobs/<root-job-dir>/start-state-plan.json

# prints: diff_only  command_log  ready  <experiment-prefix>-diff-only-command-log
# harbor run ... --ak context_mode=command_log \
#   --ak diff_path=jobs/<root-job-dir>/parent.diff \
#   --ak parent_context_path=jobs/<root-job-dir>/<parent-trial>/agent/command-log.md
```

The job name auto-suffixes to `-diff-only-command-log` so all three
`diff_only` arms (plain, transcript, command_log) can be planned from the
same root without colliding. The log file is written to
`jobs/<root-job-dir>/<parent-trial>/agent/command-log.md` at plan time —
inspect it directly before running a batch.

**Gotcha:** Terminus-2's own harness prepends retry/formatting warnings
("Previous response had warnings: ...") before the actual terminal output in
each ATIF step's observation text. `build_command_log` strips everything up
to the last `New Terminal Output:` / `Current Terminal Screen:` marker
before excerpting — without that, the excerpt is almost entirely harness
boilerplate instead of real command output. Caught by inspecting a real
generated artifact per the ticket's Validation step, not by unit tests alone
(the test fixtures use clean synthetic observation text).

Tests: `tests/test_command_log.py` (log generation: ordered entries,
chronological command→output shape, test/dependency/file annotations,
truncation, determinism, prompt-contract discipline),
`tests/test_continuations.py` (`write_command_log_context`,
`plan_start_state_baselines` wiring), `tests/test_snapshot_agent.py`
(`test_snapshot_aware_agent_command_log_uses_disclaimer_prompt`). Full
ticket: `tasks/phase-6-fixes/T009-diff-command-log.md`.

## Inspect Results

Summarize a completed Harbor job:

```bash
.venv/bin/python -m go_explore.cli summarize-job jobs/<job-name>
```

Inspect the main artifacts after a run:

```bash
python3 -m json.tool jobs/<job-name>/archive.json
tail -20 jobs/<job-name>/events.jsonl
```

Build analysis tables:

```bash
.venv/bin/python -m go_explore.cli build-analysis-tables \
  --manifest <manifest-path> \
  --job-dir jobs/<job-dir-1> \
  --job-dir jobs/<job-dir-2> \
  --continuation-report jobs/<root-job-dir>/continuation-report.json \
  --event-log jobs/<root-job-dir>/events.jsonl \
  --output-dir <analysis-dir>
```

## Current Benchmark Targets

- Claim 2: promising snapshot branching vs retry and random branch.
- Claim 1: `clean` vs `diff_only` vs `diff_only + transcript` vs `diff_only + command_log` vs `full_snapshot`.

Useful files:

- `docs/runbook.md`
- `docs/experiments/main-benchmark.md`
- `docs/experiments/viability-task-set.md`
- `docs/handoff-2026-07-27-preflight-verification-and-primary-set.md`

## Guardrails

- Do not change shared defaults just to run one experiment.
- Keep `planning_only` token budgets as labels, not hard caps.
- Record missing root archives and skipped continuations explicitly.
- Treat interrupted Harbor jobs as interrupted, not complete.
