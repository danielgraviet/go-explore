from __future__ import annotations

import json
import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from go_explore.snapshots.manager import AsyncSnapshotManager
from go_explore.snapshots.models import SnapshotRecord, context_from_atif_step
from go_explore.snapshots.policies import _changed_files_from_commands


@dataclass(frozen=True)
class ExtractedSignal:
    event_type: str
    command: str | None
    step_id: int | None = None
    duration_seconds: float | None = None
    framework: str | None = None
    tests_passed: int | None = None
    tests_failed: int | None = None
    changed_files: tuple[str, ...] = ()
    dependency_manager: str | None = None
    packages: tuple[str, ...] = ()
    metadata: dict[str, str] = field(default_factory=dict)


async def process_atif_steps(
    steps: Sequence[Mapping[str, Any]],
    manager: AsyncSnapshotManager,
    *,
    trial_name: str,
    trace_path: Path | None = None,
    environment_id: str | None = None,
    restore_ref: str | None = None,
) -> list[SnapshotRecord]:
    """Replay a step stream through the snapshot manager one step at a time."""

    records: list[SnapshotRecord] = []
    for step in steps:
        context = context_from_atif_step(
            dict(step),
            trial_name=trial_name,
            trace_path=trace_path,
            environment_id=environment_id,
            restore_ref=restore_ref,
        )
        records.extend(await manager.process_step(context))
    return records


def load_atif_trajectory_steps(trajectory_path: Path) -> list[dict[str, Any]]:
    with trajectory_path.open() as file:
        payload = json.load(file)

    steps = payload.get("steps")
    if not isinstance(steps, list):
        raise ValueError(f"Trajectory file {trajectory_path} does not contain a steps list.")

    return [dict(step) for step in steps if isinstance(step, Mapping)]


def extract_signals_from_atif_step(step: Mapping[str, Any]) -> list[ExtractedSignal]:
    """Extract simple event-level signals from one ATIF step.

    This is heuristic by design. Unknown commands are still preserved as
    `command_executed` so later analysis can improve classification without
    losing the command stream. It does not try to parse shell control flow,
    heredocs, or semantic command equivalence.
    """

    signals: list[ExtractedSignal] = []
    if step.get("source") != "agent":
        return signals

    step_id = _safe_int(step.get("step_id"))
    observation_text = _observation_text(step)

    for command, duration_seconds in _commands_from_step(step):
        changed_files = _changed_files_from_commands(command)
        signals.append(
            ExtractedSignal(
                event_type="command_executed",
                command=command,
                step_id=step_id,
                duration_seconds=duration_seconds,
                changed_files=changed_files,
            )
        )

        if changed_files:
            for path in changed_files:
                signals.append(
                    ExtractedSignal(
                        event_type="file_changed",
                        command=command,
                        step_id=step_id,
                        duration_seconds=duration_seconds,
                        changed_files=(path,),
                        metadata={"detected_by": "command_heuristic"},
                    )
                )

        test_framework = _test_framework(command)
        if test_framework is not None:
            tests_passed, tests_failed = _test_counts(observation_text)
            if (
                test_framework == "assertion"
                and tests_passed is None
                and tests_failed is None
            ):
                if _has_failure_evidence(observation_text):
                    tests_failed = 1
                else:
                    tests_passed = 1
            signals.append(
                ExtractedSignal(
                    event_type="test_run",
                    command=command,
                    step_id=step_id,
                    duration_seconds=duration_seconds,
                    framework=test_framework,
                    tests_passed=tests_passed,
                    tests_failed=tests_failed,
                )
            )

        dependency_manager, packages = _dependency_install(command)
        if dependency_manager is not None:
            signals.append(
                ExtractedSignal(
                    event_type="dependency_installed",
                    command=command,
                    step_id=step_id,
                    duration_seconds=duration_seconds,
                    dependency_manager=dependency_manager,
                    packages=packages,
                )
            )

    return signals


def extract_signals_from_atif_steps(
    steps: Sequence[Mapping[str, Any]],
) -> list[ExtractedSignal]:
    signals: list[ExtractedSignal] = []
    for step in steps:
        signals.extend(extract_signals_from_atif_step(step))
    return signals


def _commands_from_step(step: Mapping[str, Any]) -> list[tuple[str, float | None]]:
    commands: list[tuple[str, float | None]] = []
    for call in step.get("tool_calls") or ():
        if not isinstance(call, Mapping):
            continue
        if call.get("function_name") != "bash_command":
            continue
        arguments = call.get("arguments") or {}
        if not isinstance(arguments, Mapping):
            continue
        command = str(arguments.get("keystrokes", "")).strip()
        if not command:
            continue
        commands.append((command, _safe_float(arguments.get("duration"))))
    return commands


def _observation_text(step: Mapping[str, Any]) -> str:
    observation = step.get("observation") or {}
    if not isinstance(observation, Mapping):
        return ""
    return "\n".join(
        str(result.get("content", ""))
        for result in observation.get("results", [])
        if isinstance(result, Mapping)
    )


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _test_framework(command: str) -> str | None:
    lowered = command.lower()
    if "pytest" in lowered:
        return "pytest"
    if "npm test" in lowered:
        return "npm"
    if "cargo test" in lowered:
        return "cargo"
    if "go test" in lowered:
        return "go"
    if "unittest" in lowered:
        return "unittest"
    if "assert " in lowered or "assert(" in lowered:
        return "assertion"
    return None


def _test_counts(observation_text: str) -> tuple[int | None, int | None]:
    lowered = observation_text.lower()
    passed = _first_int_match(r"(\d+)\s+passed", lowered)
    failed = _first_int_match(r"(\d+)\s+failed", lowered)
    if passed is None and "passed" in lowered:
        passed = 1
    if failed is None and "failed" in lowered:
        failed = 1
    if failed is None and "assertionerror" in lowered:
        failed = 1
    return passed, failed


def _has_failure_evidence(observation_text: str) -> bool:
    lowered = observation_text.lower()
    return any(
        token in lowered
        for token in (
            "failed",
            "failure",
            "assertionerror",
            "traceback",
            "exception",
            "error:",
        )
    )


def _first_int_match(pattern: str, text: str) -> int | None:
    match = re.search(pattern, text)
    if match is None:
        return None
    return int(match.group(1))


def _dependency_install(command: str) -> tuple[str | None, tuple[str, ...]]:
    try:
        tokens = shlex.split(command)
    except ValueError:
        return None, ()
    if not tokens:
        return None, ()

    if _matches_prefix(tokens, ("pip", "install")):
        return "pip", tuple(_package_args(tokens[2:]))
    if _matches_prefix(tokens, ("python", "-m", "pip", "install")):
        return "pip", tuple(_package_args(tokens[4:]))
    if _matches_prefix(tokens, ("python3", "-m", "pip", "install")):
        return "pip", tuple(_package_args(tokens[4:]))
    if _matches_prefix(tokens, ("uv", "pip", "install")):
        return "uv-pip", tuple(_package_args(tokens[3:]))
    if _matches_prefix(tokens, ("npm", "install")):
        return "npm", tuple(_package_args(tokens[2:]))
    if _matches_prefix(tokens, ("npm", "i")):
        return "npm", tuple(_package_args(tokens[2:]))
    if _matches_prefix(tokens, ("cargo", "add")):
        return "cargo", tuple(_package_args(tokens[2:]))
    if _matches_prefix(tokens, ("go", "get")):
        return "go", tuple(_package_args(tokens[2:]))
    return None, ()


def _matches_prefix(tokens: list[str], prefix: tuple[str, ...]) -> bool:
    return tuple(tokens[: len(prefix)]) == prefix


def _package_args(tokens: list[str]) -> list[str]:
    packages: list[str] = []
    skip_next = False
    for token in tokens:
        if skip_next:
            skip_next = False
            continue
        if token in {"-r", "--requirement", "-c", "--constraint"}:
            skip_next = True
            continue
        if token.startswith("-"):
            continue
        packages.append(token)
    return packages


async def process_atif_trajectory(
    trajectory_path: Path,
    manager: AsyncSnapshotManager,
    *,
    trial_name: str,
    trace_path: Path | None = None,
    environment_id: str | None = None,
    restore_ref: str | None = None,
) -> list[SnapshotRecord]:
    """Replay a saved ATIF trajectory file through the snapshot manager."""

    return await process_atif_steps(
        load_atif_trajectory_steps(trajectory_path),
        manager,
        trial_name=trial_name,
        trace_path=trace_path or trajectory_path,
        environment_id=environment_id,
        restore_ref=restore_ref,
    )
