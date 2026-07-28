"""Deterministic, rule-based extraction of a parent ATIF trajectory into a
bounded, chronological command-log artifact for
`diff_only + command_log` children.

Distinct in shape from `transcript.py`'s categorized narrative summary: this
preserves the run as an ordered sequence of (commands, observed output)
entries - the most explicit compressed-memory condition short of actually
replaying the commands. No model call, and no execution: this only reads and
reformats an existing trajectory file.

Entries are grouped by ATIF step, not by individual command: Terminus-2
batches multiple commands into one turn and returns one combined terminal
observation for the whole batch, so showing a separate "per-command" excerpt
would just repeat the same blob under every command in that batch, implying
a precision the underlying data doesn't have.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path

from go_explore.snapshots.models import context_from_atif_step
from go_explore.snapshots.replay import (
    ExtractedSignal,
    extract_signals_from_atif_step,
    load_atif_trajectory_steps,
)
from go_explore.snapshots.transcript import ParentOutcome

COMMAND_LOG_MAX_CHARS = 6000
MAX_ENTRIES_SHOWN = 40
OUTPUT_EXCERPT_MAX_CHARS = 300

# Terminus-2's own harness prepends retry/formatting warnings before the
# actual terminal output; strip everything up to the last of these markers
# so the excerpt shows real command output, not harness boilerplate.
_OBSERVATION_MARKERS = ("New Terminal Output:", "Current Terminal Screen:")


def build_command_log(
    trajectory_path: Path,
    *,
    trial_name: str,
    task_name: str | None,
    outcome: ParentOutcome,
    reward: float | None,
    max_chars: int = COMMAND_LOG_MAX_CHARS,
    max_commands: int = MAX_ENTRIES_SHOWN,
) -> str:
    """Turn a parent's `trajectory.json` into a bounded command+output log.

    `max_commands` bounds the number of log entries (one per ATIF step with
    at least one command), not raw individual commands - a step that batches
    several commands still counts as one entry, since it shares one observed
    output. Rule-based only, reusing `load_atif_trajectory_steps` and
    `extract_signals_from_atif_step` (no bespoke parser). Never raises - a
    missing or malformed trajectory degrades to a header-only log.
    """
    try:
        steps = load_atif_trajectory_steps(trajectory_path)
    except (OSError, ValueError):
        steps = []

    agent_steps = [step for step in steps if step.get("source") == "agent"]

    entries: list[str] = []
    total_commands = 0
    shown_commands = 0
    for step in agent_steps:
        signals = extract_signals_from_atif_step(step)
        command_signals = [s for s in signals if s.event_type == "command_executed"]
        if not command_signals:
            continue

        total_commands += len(command_signals)
        if len(entries) >= max_commands:
            continue

        observation = context_from_atif_step(
            dict(step), trial_name=trial_name
        ).observation_text
        excerpt = _clean_observation(observation)[:OUTPUT_EXCERPT_MAX_CHARS]

        test_signals = [s for s in signals if s.event_type == "test_run"]
        dependency_signals = [s for s in signals if s.event_type == "dependency_installed"]
        changed_files = _ordered_unique_files(signals)

        lines = [f"$ {signal.command}" for signal in command_signals]
        lines[0] = f"{len(entries) + 1:03d}. {lines[0]}"
        lines[1:] = [f"     {line}" for line in lines[1:]]
        if excerpt:
            lines.append(f"    -> {excerpt}")

        for test_signal in test_signals:
            counts = []
            if test_signal.tests_passed is not None:
                counts.append(f"{test_signal.tests_passed} passed")
            if test_signal.tests_failed is not None:
                counts.append(f"{test_signal.tests_failed} failed")
            if counts:
                lines.append(f"    [test result: {', '.join(counts)}]")

        for dependency_signal in dependency_signals:
            packages = ", ".join(dependency_signal.packages) or "(unspecified)"
            lines.append(
                f"    [dependency install: {dependency_signal.dependency_manager} {packages}]"
            )

        if changed_files:
            lines.append(f"    [files changed: {', '.join(changed_files)}]")

        entries.append("\n".join(lines))
        shown_commands += len(command_signals)

    header = [
        f"# Parent command log: {task_name or 'unknown task'}",
        f"trial: {trial_name}",
        f"outcome: {outcome} (reward: {reward if reward is not None else 'unknown'})",
        "",
    ]
    body = entries if entries else ["(no commands recorded)"]
    if total_commands > shown_commands:
        body.append(f"... ({total_commands - shown_commands} more commands not shown)")

    text = "\n".join(header + body).strip() + "\n"
    return _truncate(text, max_chars)


def _clean_observation(text: str) -> str:
    """Strip harness retry/formatting-warning preamble, keeping only the
    actual terminal content that follows the last marker present."""
    cutoff = -1
    for marker in _OBSERVATION_MARKERS:
        index = text.rfind(marker)
        if index != -1:
            cutoff = max(cutoff, index + len(marker))
    cleaned = text[cutoff:] if cutoff != -1 else text
    return re.sub(r"\n{3,}", "\n\n", cleaned.strip())


def _ordered_unique_files(signals: Sequence[ExtractedSignal]) -> list[str]:
    seen: list[str] = []
    for signal in signals:
        if signal.event_type != "file_changed":
            continue
        for path in signal.changed_files:
            if path not in seen:
                seen.append(path)
    return seen


_TRUNCATION_NOTE = "\n... (command log truncated)\n"


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - len(_TRUNCATION_NOTE)] + _TRUNCATION_NOTE
