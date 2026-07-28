from __future__ import annotations

import json
import shlex
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from go_explore.snapshots.replay import ExtractedSignal

DISCOVERY_COMMANDS = {
    "cat",
    "find",
    "grep",
    "head",
    "ls",
    "rg",
    "sed",
    "tail",
    "tree",
}


@dataclass(frozen=True)
class CommandObservation:
    """One command-like event normalized for repeated-work analysis."""

    run_id: str
    command: str
    event_types: tuple[str, ...] = ("command_executed",)

    @property
    def command_prefix(self) -> str:
        return command_prefix(self.command)

    @property
    def categories(self) -> tuple[str, ...]:
        categories: list[str] = []
        if "dependency_installed" in self.event_types or is_setup_command(self.command):
            categories.append("setup")
        if "test_run" in self.event_types or is_test_command(self.command):
            categories.append("test")
        if is_discovery_command(self.command):
            categories.append("discovery")
        return tuple(categories)


@dataclass(frozen=True)
class RunRepeatedWorkMetrics:
    run_id: str
    total_commands: int
    repeated_command_count: int = 0
    repeated_prefix_count: int = 0
    repeated_setup_count: int = 0
    repeated_test_count: int = 0
    repeated_discovery_count: int = 0
    repeated_sibling_command_count: int = 0
    repeated_sibling_prefix_count: int = 0
    repeated_setup_commands: tuple[str, ...] = ()
    repeated_test_commands: tuple[str, ...] = ()
    repeated_discovery_commands: tuple[str, ...] = ()
    repeated_command_prefixes: tuple[str, ...] = ()

    @property
    def repeated_setup_score(self) -> int:
        return (
            self.repeated_setup_count
            + self.repeated_test_count
            + self.repeated_discovery_count
        )

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "total_commands": self.total_commands,
            "repeated_command_count": self.repeated_command_count,
            "repeated_prefix_count": self.repeated_prefix_count,
            "repeated_setup_count": self.repeated_setup_count,
            "repeated_test_count": self.repeated_test_count,
            "repeated_discovery_count": self.repeated_discovery_count,
            "repeated_sibling_command_count": self.repeated_sibling_command_count,
            "repeated_sibling_prefix_count": self.repeated_sibling_prefix_count,
            "repeated_setup_score": self.repeated_setup_score,
            "repeated_setup_commands": list(self.repeated_setup_commands),
            "repeated_test_commands": list(self.repeated_test_commands),
            "repeated_discovery_commands": list(self.repeated_discovery_commands),
            "repeated_command_prefixes": list(self.repeated_command_prefixes),
        }


@dataclass(frozen=True)
class RepeatedWorkReport:
    runs: tuple[RunRepeatedWorkMetrics, ...]
    heuristic_notes: tuple[str, ...] = field(
        default=(
            "Commands are compared by exact normalized text and first-token prefix.",
            "Setup, test, and discovery categories are command-pattern heuristics.",
            "No semantic equivalence is attempted.",
        )
    )

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "go-explore-repeated-work-v1",
            "heuristic_notes": list(self.heuristic_notes),
            "runs": [run.to_json_dict() for run in self.runs],
        }


def command_prefix(command: str) -> str:
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()
    if not tokens:
        return ""
    if len(tokens) >= 3 and tokens[:3] in (
        ["python", "-m", "pip"],
        ["python3", "-m", "pip"],
    ):
        return " ".join(tokens[:4]) if len(tokens) >= 4 else " ".join(tokens)
    if len(tokens) >= 2 and tokens[:2] in (
        ["cargo", "test"],
        ["cargo", "add"],
        ["go", "get"],
        ["go", "test"],
        ["npm", "install"],
        ["npm", "test"],
        ["pip", "install"],
        ["uv", "pip"],
    ):
        if tokens[:2] == ["uv", "pip"] and len(tokens) >= 3:
            return " ".join(tokens[:3])
        return " ".join(tokens[:2])
    return tokens[0]


def is_setup_command(command: str) -> bool:
    return command_prefix(command) in {
        "cargo add",
        "go get",
        "npm install",
        "pip install",
        "python -m pip install",
        "python3 -m pip install",
        "uv pip install",
    }


def is_test_command(command: str) -> bool:
    return command_prefix(command) in {
        "cargo test",
        "go test",
        "npm test",
        "pytest",
        "python",
    } and (
        "pytest" in command
        or "unittest" in command
        or command_prefix(command) in {"cargo test", "go test", "npm test"}
    )


def is_discovery_command(command: str) -> bool:
    prefix = command_prefix(command)
    return prefix in DISCOVERY_COMMANDS


def repeated_work_from_signals(
    run_signals: Mapping[str, Sequence[ExtractedSignal]],
) -> RepeatedWorkReport:
    observations: list[CommandObservation] = []
    for run_id, signals in run_signals.items():
        observations.extend(_observations_from_signals(run_id, signals))
    return compute_repeated_work(observations)


def repeated_work_from_event_logs(
    paths: Sequence[Path],
) -> RepeatedWorkReport:
    observations: list[CommandObservation] = []
    for path in paths:
        observations.extend(_observations_from_events(read_jsonl_events(path)))
    return compute_repeated_work(observations)


def read_jsonl_events(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    if not path.exists():
        return events
    for line in path.read_text().splitlines():
        if line.strip():
            events.append(json.loads(line))
    return events


def compute_repeated_work(
    observations: Sequence[CommandObservation],
) -> RepeatedWorkReport:
    observations_by_run: dict[str, list[CommandObservation]] = defaultdict(list)
    for observation in observations:
        observations_by_run[observation.run_id].append(observation)

    command_counts = Counter(observation.command for observation in observations)
    prefix_counts = Counter(observation.command_prefix for observation in observations)
    runs_by_command = _runs_by_key(observations, key="command")
    runs_by_prefix = _runs_by_key(observations, key="prefix")

    metrics: list[RunRepeatedWorkMetrics] = []
    for run_id in sorted(observations_by_run):
        run_observations = observations_by_run[run_id]
        metrics.append(
            _metrics_for_run(
                run_id,
                run_observations,
                command_counts=command_counts,
                prefix_counts=prefix_counts,
                runs_by_command=runs_by_command,
                runs_by_prefix=runs_by_prefix,
            )
        )

    return RepeatedWorkReport(runs=tuple(metrics))


def write_repeated_work_report(report: RepeatedWorkReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_json_dict(), indent=2) + "\n")


def _observations_from_signals(
    run_id: str,
    signals: Sequence[ExtractedSignal],
) -> list[CommandObservation]:
    event_types_by_command: dict[str, set[str]] = defaultdict(set)
    for signal in signals:
        if signal.command is None:
            continue
        if signal.event_type in {
            "command_executed",
            "dependency_installed",
            "test_run",
        }:
            event_types_by_command[_normalize_command(signal.command)].add(
                signal.event_type
            )

    return [
        CommandObservation(
            run_id=run_id,
            command=command,
            event_types=tuple(sorted(event_types)),
        )
        for command, event_types in event_types_by_command.items()
    ]


def _observations_from_events(
    events: Iterable[Mapping[str, Any]],
) -> list[CommandObservation]:
    event_types_by_run_command: dict[tuple[str, str], set[str]] = defaultdict(set)
    for event in events:
        event_type = str(event.get("event_type") or "")
        if event_type not in {
            "command_executed",
            "dependency_installed",
            "test_run",
        }:
            continue
        command = event.get("command")
        run_id = event.get("run_id")
        if not isinstance(command, str) or not isinstance(run_id, str):
            continue
        event_types_by_run_command[
            (run_id, _normalize_command(command))
        ].add(event_type)

    return [
        CommandObservation(
            run_id=run_id,
            command=command,
            event_types=tuple(sorted(event_types)),
        )
        for (run_id, command), event_types in event_types_by_run_command.items()
    ]


def _metrics_for_run(
    run_id: str,
    observations: Sequence[CommandObservation],
    *,
    command_counts: Counter[str],
    prefix_counts: Counter[str],
    runs_by_command: Mapping[str, set[str]],
    runs_by_prefix: Mapping[str, set[str]],
) -> RunRepeatedWorkMetrics:
    repeated_commands = sorted(
        {
            observation.command
            for observation in observations
            if command_counts[observation.command] > 1
        }
    )
    repeated_prefixes = sorted(
        {
            observation.command_prefix
            for observation in observations
            if observation.command_prefix
            and prefix_counts[observation.command_prefix] > 1
        }
    )
    sibling_commands = sorted(
        {
            observation.command
            for observation in observations
            if len(runs_by_command[observation.command] - {run_id}) > 0
        }
    )
    sibling_prefixes = sorted(
        {
            observation.command_prefix
            for observation in observations
            if observation.command_prefix
            and len(runs_by_prefix[observation.command_prefix] - {run_id}) > 0
        }
    )

    repeated_setup = _repeated_category_commands(
        observations,
        repeated_commands,
        category="setup",
    )
    repeated_tests = _repeated_category_commands(
        observations,
        repeated_commands,
        category="test",
    )
    repeated_discovery = _repeated_category_commands(
        observations,
        repeated_commands,
        category="discovery",
    )

    return RunRepeatedWorkMetrics(
        run_id=run_id,
        total_commands=len(observations),
        repeated_command_count=len(repeated_commands),
        repeated_prefix_count=len(repeated_prefixes),
        repeated_setup_count=len(repeated_setup),
        repeated_test_count=len(repeated_tests),
        repeated_discovery_count=len(repeated_discovery),
        repeated_sibling_command_count=len(sibling_commands),
        repeated_sibling_prefix_count=len(sibling_prefixes),
        repeated_setup_commands=tuple(repeated_setup),
        repeated_test_commands=tuple(repeated_tests),
        repeated_discovery_commands=tuple(repeated_discovery),
        repeated_command_prefixes=tuple(repeated_prefixes),
    )


def _repeated_category_commands(
    observations: Sequence[CommandObservation],
    repeated_commands: Sequence[str],
    *,
    category: str,
) -> list[str]:
    repeated = set(repeated_commands)
    return sorted(
        {
            observation.command
            for observation in observations
            if observation.command in repeated and category in observation.categories
        }
    )


def _runs_by_key(
    observations: Sequence[CommandObservation],
    *,
    key: str,
) -> dict[str, set[str]]:
    runs: dict[str, set[str]] = defaultdict(set)
    for observation in observations:
        if key == "command":
            runs[observation.command].add(observation.run_id)
        elif key == "prefix":
            runs[observation.command_prefix].add(observation.run_id)
        else:
            raise ValueError(f"Unknown repeated-work key: {key}")
    return runs


def _normalize_command(command: str) -> str:
    return "\n".join(line.strip() for line in command.splitlines()).strip()
