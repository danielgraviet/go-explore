"""Deterministic, rule-based compression of a parent ATIF trajectory into a
short text-memory artifact for `diff_only + full_transcript_summary` children.

No model call: an LLM-written summary would add cost, variance, and a second
model choice to a comparison that is supposed to isolate representation
quality (code diff + text memory) from those confounds.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

from go_explore.snapshots.models import context_from_atif_step
from go_explore.snapshots.replay import (
    ExtractedSignal,
    extract_signals_from_atif_step,
    load_atif_trajectory_steps,
)

TRANSCRIPT_MAX_CHARS = 4000
MAX_COMMANDS_SHOWN = 25
MAX_FILES_SHOWN = 20
OBSERVATION_MAX_CHARS = 500

ParentOutcome = Literal["solved", "failed", "timed_out", "unknown"]


def parent_outcome(reward: float | None, exception_type: str | None) -> ParentOutcome:
    """Classify the parent's result using only recorded facts - no inference
    about *why* it ended that way."""
    if exception_type and "timeout" in exception_type.lower():
        return "timed_out"
    if reward is None:
        return "unknown"
    return "solved" if reward == 1.0 else "failed"


def build_transcript_summary(
    trajectory_path: Path,
    *,
    trial_name: str,
    task_name: str | None,
    outcome: ParentOutcome,
    reward: float | None,
    max_chars: int = TRANSCRIPT_MAX_CHARS,
) -> str:
    """Turn a parent's `trajectory.json` into a compact markdown note.

    Rule-based only: reuses `load_atif_trajectory_steps` and
    `extract_signals_from_atif_step` (the same heuristics used for snapshot
    interestingness scoring) rather than a bespoke parser. Never raises - a
    missing or malformed trajectory degrades to a header-only summary.
    """
    try:
        steps = load_atif_trajectory_steps(trajectory_path)
    except (OSError, ValueError):
        steps = []

    agent_steps = [step for step in steps if step.get("source") == "agent"]
    step_signals = [
        (step, extract_signals_from_atif_step(step)) for step in agent_steps
    ]
    signals = [signal for _, signals_for_step in step_signals for signal in signals_for_step]

    commands = [s for s in signals if s.event_type == "command_executed"]
    test_runs = [s for s in signals if s.event_type == "test_run"]
    dependency_installs = [s for s in signals if s.event_type == "dependency_installed"]
    changed_files = _ordered_unique_files(signals)

    lines: list[str] = [
        f"# Parent attempt summary: {task_name or 'unknown task'}",
        f"trial: {trial_name}",
        f"outcome: {outcome} (reward: {reward if reward is not None else 'unknown'})",
        "",
    ]
    lines.extend(_command_lines(commands))
    lines.extend(_file_lines(changed_files))
    lines.extend(_test_run_lines(test_runs))
    lines.extend(_dependency_lines(dependency_installs))
    lines.extend(_last_observation_lines(step_signals, trial_name=trial_name))

    text = "\n".join(lines).strip() + "\n"
    return _truncate(text, max_chars)


def _ordered_unique_files(signals: Sequence[ExtractedSignal]) -> list[str]:
    seen: list[str] = []
    for signal in signals:
        if signal.event_type != "file_changed":
            continue
        for path in signal.changed_files:
            if path not in seen:
                seen.append(path)
    return seen


def _command_lines(commands: Sequence[ExtractedSignal]) -> list[str]:
    if not commands:
        return []
    shown = commands[:MAX_COMMANDS_SHOWN]
    lines = ["## Commands run (in order)"]
    lines.extend(f"- {signal.command}" for signal in shown)
    if len(commands) > len(shown):
        lines.append(f"- ... ({len(commands) - len(shown)} more commands not shown)")
    lines.append("")
    return lines


def _file_lines(changed_files: Sequence[str]) -> list[str]:
    if not changed_files:
        return []
    shown = changed_files[:MAX_FILES_SHOWN]
    lines = ["## Files touched"]
    lines.extend(f"- {path}" for path in shown)
    if len(changed_files) > len(shown):
        lines.append(f"- ... ({len(changed_files) - len(shown)} more files not shown)")
    lines.append("")
    return lines


def _test_run_lines(test_runs: Sequence[ExtractedSignal]) -> list[str]:
    if not test_runs:
        return []
    lines = ["## Test runs (observed, not inferred)"]
    for signal in test_runs:
        counts = []
        if signal.tests_passed is not None:
            counts.append(f"{signal.tests_passed} passed")
        if signal.tests_failed is not None:
            counts.append(f"{signal.tests_failed} failed")
        counts_text = ", ".join(counts) if counts else "result unknown"
        lines.append(f"- `{signal.command}` -> {counts_text}")
    lines.append("")
    return lines


def _dependency_lines(dependency_installs: Sequence[ExtractedSignal]) -> list[str]:
    if not dependency_installs:
        return []
    lines = ["## Dependency/service setup"]
    for signal in dependency_installs:
        packages = ", ".join(signal.packages) if signal.packages else "(unspecified)"
        lines.append(f"- {signal.dependency_manager}: {packages}")
    lines.append("")
    return lines


def _last_observation_lines(
    step_signals: Sequence[tuple[Mapping[str, Any], Sequence[ExtractedSignal]]],
    *,
    trial_name: str,
) -> list[str]:
    last_test_step = None
    for step, signals_for_step in step_signals:
        if any(signal.event_type == "test_run" for signal in signals_for_step):
            last_test_step = step

    if last_test_step is None:
        return []

    observation = context_from_atif_step(
        dict(last_test_step), trial_name=trial_name
    ).observation_text.strip()
    if not observation:
        return []

    return [
        "## Last observed test/verifier output",
        observation[:OBSERVATION_MAX_CHARS],
        "",
    ]


_TRUNCATION_NOTE = "\n... (transcript truncated)\n"


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - len(_TRUNCATION_NOTE)] + _TRUNCATION_NOTE
