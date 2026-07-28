# Handoff: Claim 1 arms built, ready for first pilot, 2026-07-28

Written for whoever picks this up tomorrow. Read this first. Related docs:
`docs/COMMANDS.md` (exact commands for every arm below), `docs/essay.md`
(Claim 1 framing), `docs/token-cost-estimate-2026-07-28.md` (budget
guardrails - read before spending anything).

## Where things stand

All six Claim 1 start-state arms now exist and are individually validated
against real (not synthetic) trajectory data. **Nothing has been run as a
comparative pilot yet** - every validation so far has been one arm at a
time, proving the mechanism works, not comparing arms against each other.

### Implementation status

| Arm | `start_state_type` | `context_mode` | Status |
| --- | --- | --- | --- |
| Clean | `clean` | `original_task_only` | Implemented, long-standing |
| Diff only | `diff_only` | `original_task_only` | Implemented (T007), merged to `main` |
| Diff + transcript | `diff_only` | `full_transcript_summary` | Implemented (T008), merged to `main` |
| Diff + command log | `diff_only` | `command_log` | Implemented (T009), merged to `main` |
| Command replay | `command_replay` | `original_task_only` (always) | Implemented (T010), **on branch `dg/replayed-env`, not yet merged** |
| Full snapshot | `full_snapshot` | `none` / `parent_summary` / `critical_parent_summary` | Implemented, long-standing |

**First thing to do**: check `git status` and `git log` on `dg/replayed-env`
- T010 is code-complete and all 282 tests pass, but it was never committed
or merged. Decide whether to commit/PR it before or as part of tomorrow's
pilot work; the pilot needs `command_replay` to be on `main` (or you run
the pilot from that branch directly).

Every arm is planned the same way, through one function:
`plan_start_state_baselines()` in `go_explore/continuations.py`, exposed via
`python -m go_explore.cli plan-start-state-baselines`. It only plans and
prints a Harbor command - it never executes anything itself. See
`docs/COMMANDS.md`'s "Start-State Baselines" section and its three
sub-sections (`diff_only + transcript`, `diff_only + command_log`,
`command_replay`) for the exact mock commands for each arm, including every
flag.

### What's been validated so far (mechanism, not comparison)

All done as single, cheap, one-off live Harbor runs against Daytona
(real spend, but small - each run was a few cents to ~$0.17):

- **`diff_only`**: ran on `fix-git` twice. First attempt used a diff whose
  target path didn't match the task's actual repo location and taught us
  `git apply`'s cwd is `environment.task_env_config.workdir`, not always the
  task's `/app` root. Second attempt (correct path) showed the diff-created
  file appearing in the agent's very first `git status`, before the agent
  did anything - proof the diff applies in `setup()`, strictly before the
  agent's first turn.
- **`diff_only + transcript`**: ran on `fix-git`. The agent's own reasoning
  visibly echoed the injected transcript's suggested resolution
  (`git checkout --theirs`), proving the transcript was both received and
  used, not just present in the prompt unread.
- **`diff_only + command_log`**: local artifact inspection only (no live
  run) against a real `fix-git` trajectory. Caught and fixed a real bug
  where Terminus-2's own harness retry/warning boilerplate was drowning out
  actual command output in the excerpts - fixed by stripping everything
  before the last `New Terminal Output:` / `Current Terminal Screen:`
  marker.
- **`command_replay`**: ran on `build-cython-ext` (the only local trajectory
  with real, safe-to-replay `pip install` commands). Confirmed via the
  agent's own later `pip install -e .` output: `Requirement already
  satisfied: numpy ... (2.3.0)` - direct proof the replayed package was
  already installed before the agent did anything. Task itself scored
  reward 0.0 (build-cython-ext is genuinely hard for Haiku - expected, not
  a bug). Replay overhead was ~6.9s against an ~714s total run (~1%),
  confirmed cleanly separated from agent solve time. Cost $0.173, 11m54s.
- **A real, live regression was found and fixed along the way**: T008's
  first live validation revealed `SnapshotAwareTerminus2.__init__` wasn't
  forwarding `diff_path` to `SnapshotAwareAgent`, so `--ak diff_path=...`
  silently did nothing. Fixed, and a regression test was added *before* the
  same mistake could repeat for `replay_manifest_path` in T010 - check
  `test_snapshot_aware_terminus2_accepts_replay_manifest_path_without_wrapped_leak`
  in `tests/test_snapshot_agent.py` if you add a new arm kwarg: it must be
  forwarded through **both** `SnapshotAwareTerminus2.__init__` and
  `SnapshotAwareOracle.__init__` in `go_explore/agents/factory.py`, or it
  silently no-ops with no error.

### Where the automated test coverage lives

`tests/test_diff_only.py`, `tests/test_transcript.py`,
`tests/test_command_log.py`, `tests/test_command_replay.py` (mechanics of
each executor/selector), plus wiring tests spread across
`tests/test_continuations.py`, `tests/test_snapshot_agent.py`,
`tests/test_cli.py`. 282 tests passing as of T010. Run `.venv/bin/python -m
pytest -q` to confirm before doing anything else.

## What to do next (priority order)

1. **Sort out the `dg/replayed-env` branch** (commit/PR/merge) so all six
   arms are runnable from `main`.

2. **Run the actual comparative pilot** - this is the part that hasn't
   happened yet. My working idea (confirm or adjust before spending):
   run all six arms from the *same* parent root(s), on a small, genuinely
   cheap task set, one seed, Haiku only, then build one set of analysis
   tables and read them side by side.

   Task-set tension worth resolving before starting, not after:
   - `fix-git` is the cheapest, most-validated task in this project
     (~$0.02-0.03, ~2 min per trial) - but it's a git-merge-conflict task
     with **no dependency installs**, so `command_replay` would plan zero
     commands against it. It's a good task for `clean` / `diff_only` /
     `diff_only + transcript` / `diff_only + command_log` / `full_snapshot`,
     but not a meaningful test of `command_replay`.
   - `build-cython-ext` (the ticket's suggested pilot task, and the one
     already validated for `command_replay`) has real dependency installs
     but is **not cheap** - $0.17 and ~12 min for a single Haiku trial that
     didn't even solve the task. Running 6 arms x 1 seed here is a real
     cost commitment, not a smoke test.
   - `docs/experiments/viability-task-set.md` has a vetted 6-task list
     (`regex-log`, `build-cython-ext`, `git-leak-recovery`,
     `sqlite-db-truncate`, `sanitize-git-repo`, `large-scale-text-editing`)
     plus fallbacks, already used for prior Claim 2 work - reuse that
     vetting rather than picking new tasks from scratch.
   - `docs/token-cost-estimate-2026-07-28.md`'s Spend Control Plan (written
     today, read it) explicitly recommends starting with "the smallest
     useful slice" of `clean`/`diff_only`/`full_snapshot` on Haiku, one
     seed, and calls out `qemu-*` as a high-cost outlier to avoid early.
     Its own planning table estimates a 6-task, 3-start-state, 1-seed Claim
     1 pilot at **$10-$40 on Haiku** - now double the start-state count
     (six arms instead of three) and budget accordingly, or narrow the task
     count to compensate.

   Suggested resolution (not decided - flag to the user first): use 2-3
   tasks from the viability list that have both git-trackable diffs *and*
   real dependency installs (check trajectories under `jobs/` first, the
   way this session did for `build-cython-ext`, before assuming), run all
   six arms x 1 seed x Haiku on each, and treat `fix-git` as a zero-cost
   sanity check on the side rather than part of the real comparison.

3. **Build analysis tables and review.**
   `python -m go_explore.cli build-analysis-tables --manifest <plan.json>
   --job-dir jobs/<...> [...] --output-dir <analysis-dir>` (see
   `docs/COMMANDS.md`'s "Inspect Results" section for the full flag list).
   Compare, per task: solve rate, `total_tokens`/`cost_usd`,
   `duration_seconds`, and for `full_snapshot` specifically
   `restore_overhead_seconds`/`snapshot_overhead_seconds` (already
   dedicated columns). `command_replay`'s own overhead
   (`total_replay_seconds`) is **not** a dedicated analysis-table column
   yet - it only lives in each trial's `replay-result.json` artifact. That
   was an explicit, discussed decision: in the one pilot run so far it was
   ~1% of total wall-clock, so wiring it into `analysis_tables.py` was
   deferred until the real ablation shows it's actually load-bearing.
   Revisit that decision once real pilot data exists - if replay overhead
   turns out to vary meaningfully by task, it should probably get a
   dedicated column before the primary run.

4. **Write the short memo** each of T008/T009/T010's tickets asks for
   ("does transcript/command-log/replay memory help, or just add cost/
   risk, relative to `diff_only` and `full_snapshot`") - this can only be
   written once step 3's tables exist. Don't guess at this from the
   single-arm validation runs; none of them are comparable to each other
   (different tasks, no shared baseline).

## Decisions made today (with the user, explicit)

- `command_replay` failures are **best-effort, never abort the run** -
  a failed/skipped replay command is recorded per-entry but the agent
  always starts. This is different from `diff_only`'s `DiffApplyFailed`,
  which does abort - the reasoning is that a diff either applies or it
  doesn't (binary, all-or-nothing), while replay is inherently an
  approximation (some setup commands working is still useful signal).
- `command_replay`'s initial allowlist is **dependency installs only** -
  no build commands, no service starts, nothing else. Confirmed narrow on
  purpose; broadening it is explicitly a follow-up, not something to do
  as part of the pilot.
- `total_replay_seconds` analysis-table wiring was explicitly deferred
  pending real pilot data (see item 3 above) rather than built speculatively.

## Housekeeping

- Local `jobs/` dir already has real trajectories worth reusing for task
  selection in step 2 - e.g. `grep`-ing for `pip install` across
  `jobs/**/trajectory.json` is how `build-cython-ext` got picked for the
  `command_replay` validation. Check what's already there before running
  fresh root jobs just to get parent trajectories.
- `docs/token-cost-estimate-2026-07-28.md` was edited by someone/something
  else today mid-session (a "Spend Control Plan" section appeared) - it's
  current and worth trusting, just flagging that it wasn't static
  throughout today's work.
- An untracked dir,
  `docs/experiments/main-benchmark/analysis/phase4-primary-qemu-alpine-ssh-001/`,
  showed up in `git status` during this session, not from this work -
  investigate before assuming it's safe to ignore or delete.
