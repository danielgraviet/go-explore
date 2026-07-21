# Repeated Work Metrics

These metrics are heuristics for Phase 3/4 analysis. They are meant to be
easy to inspect and disagree with, not a semantic command-equivalence model.

## Inputs

The analyzer can consume either:

- extracted ATIF signals from `go_explore.snapshots.replay`, or
- JSONL event logs containing `command_executed`, `test_run`, and
  `dependency_installed` events.

Snapshot events are ignored for repeated-work counts.

## Counts

For each run, the report records:

| Field | Meaning |
| --- | --- |
| `total_commands` | Number of normalized command observations for the run. |
| `repeated_command_count` | Exact normalized commands that appear more than once globally. |
| `repeated_prefix_count` | Command prefixes that appear more than once globally. |
| `repeated_setup_count` | Repeated exact install/setup commands. |
| `repeated_test_count` | Repeated exact test commands. |
| `repeated_discovery_count` | Repeated exact file-discovery commands such as `rg`, `find`, `ls`, and `cat`. |
| `repeated_sibling_command_count` | Exact commands also seen in another run. |
| `repeated_sibling_prefix_count` | Command prefixes also seen in another run. |
| `repeated_setup_score` | `setup + test + discovery` repeated counts. |

## Heuristic Rules

Commands are normalized by trimming whitespace on each line. Exact-command
repeat means the normalized command text matches exactly.

Prefix repeat uses the command family, usually the first token. Common
multi-token families such as `pip install`, `uv pip install`, `npm install`,
`go test`, and `cargo test` are preserved.

Setup commands are package or dependency install commands. Test commands are
common test runners such as `pytest`, `npm test`, `go test`, `cargo test`, and
`python -m unittest`. Discovery commands are simple file or text inspection
commands such as `rg`, `grep`, `find`, `ls`, `cat`, `head`, and `tail`.

## Non-Goals

The metric does not attempt semantic equivalence. These commands are treated as
different exact commands even if a human sees them as similar:

- `pytest tests -q`
- `python -m pytest tests -q`
- `pytest tests/test_a.py -q`

The prefix metric may still count them as repeated work when they share a
command family. That makes the report useful as a first-pass signal without
hiding the raw commands.
