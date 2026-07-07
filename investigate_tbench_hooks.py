from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


CONTROL_TOKENS = {"q", "c-c", "enter"}


def _joined_keystrokes(step: dict[str, Any]) -> list[str]:
    commands: list[str] = []
    for call in step.get("tool_calls", []) or []:
        if not isinstance(call, dict):
            continue
        if call.get("function_name") != "bash_command":
            continue

        arguments = call.get("arguments") or {}
        if not isinstance(arguments, dict):
            continue

        keystrokes = arguments.get("keystrokes")
        if isinstance(keystrokes, str):
            commands.append(keystrokes)

    return commands


def _is_control_only(commands: list[str]) -> bool:
    normalized = [command.strip().lower() for command in commands if command.strip()]
    return bool(normalized) and all(command in CONTROL_TOKENS for command in normalized)


def analyze_trajectory(trajectory_path: Path) -> None:
    payload = json.loads(trajectory_path.read_text())
    steps = payload.get("steps", [])

    if not isinstance(steps, list):
        raise ValueError(f"{trajectory_path} does not contain a steps list")

    agent_steps = 0
    snapshot_eligible = 0

    print(f"trajectory: {trajectory_path}")
    print(f"schema: {payload.get('schema_version', '<unknown>')}")
    print("")

    for step in steps:
        if not isinstance(step, dict):
            continue

        step_id = step.get("step_id", "?")
        source = step.get("source", "")
        commands = _joined_keystrokes(step)
        eligible = source == "agent" and bool(commands) and not _is_control_only(commands)

        if source == "agent":
            agent_steps += 1
        if eligible:
            snapshot_eligible += 1

        print(f"step {step_id} | source={source!r} | commands={len(commands)} | eligible={eligible}")
        print("  hook surface: tool_calls[*].arguments.keystrokes")
        for index, command in enumerate(commands, start=1):
            print(f"    {index}. {command!r}")
        if not commands:
            print("    <no bash_command tool calls>")
        if _is_control_only(commands):
            print("    control-only batch: true")
        print("")

    print(f"agent_steps={agent_steps}")
    print(f"snapshot_eligible_batches={snapshot_eligible}")


def _default_trajectory() -> Path | None:
    candidates = sorted(Path("jobs").glob("**/agent/trajectory.json"))
    return candidates[-1] if candidates else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect ATIF trajectories and command hook batches.")
    parser.add_argument(
        "trajectory",
        nargs="?",
        type=Path,
        default=_default_trajectory(),
        help="Path to a trajectory.json file. Defaults to the newest job trajectory under jobs/.",
    )
    args = parser.parse_args()

    if args.trajectory is None:
        raise SystemExit("No trajectory file found. Pass a path explicitly.")

    analyze_trajectory(args.trajectory)


if __name__ == "__main__":
    main()
