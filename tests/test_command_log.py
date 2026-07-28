"""Tests for go_explore.snapshots.command_log.build_command_log."""

from __future__ import annotations

import json
from pathlib import Path

from go_explore.snapshots.command_log import build_command_log


def _write_atif_trajectory(path: Path, steps: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"steps": steps}))


def _rich_trajectory_steps() -> list[dict]:
    return [
        {
            "step_id": 1,
            "source": "agent",
            "tool_calls": [
                {
                    "function_name": "bash_command",
                    "arguments": {"keystrokes": "pip install requests\n"},
                }
            ],
            "observation": {"results": [{"content": "Successfully installed requests"}]},
        },
        {
            "step_id": 2,
            "source": "agent",
            "tool_calls": [
                {
                    "function_name": "bash_command",
                    "arguments": {"keystrokes": "sed -i 's/toml/json/' config.py\n"},
                }
            ],
            "observation": {"results": [{"content": "edited"}]},
        },
        {
            "step_id": 3,
            "source": "agent",
            "tool_calls": [
                {
                    "function_name": "bash_command",
                    "arguments": {"keystrokes": "pytest tests -q\n"},
                }
            ],
            "observation": {
                "results": [
                    {
                        "content": (
                            "2 passed, 1 failed\n"
                            "FAILED test_parser.py::test_toml_config"
                        )
                    }
                ]
            },
        },
    ]


def test_build_command_log_covers_all_required_fields(tmp_path):
    trajectory_path = tmp_path / "trajectory.json"
    _write_atif_trajectory(trajectory_path, _rich_trajectory_steps())

    text = build_command_log(
        trajectory_path,
        trial_name="fix-git__root",
        task_name="fix-git",
        outcome="failed",
        reward=0.0,
    )

    assert "fix-git" in text
    assert "fix-git__root" in text
    assert "outcome: failed (reward: 0.0)" in text
    # ordered commands, numbered
    assert "001. $ pip install requests" in text
    assert "002. $ sed -i 's/toml/json/' config.py" in text
    assert "003. $ pytest tests -q" in text
    # observed output attached inline, per command
    assert "Successfully installed requests" in text
    assert "2 passed, 1 failed" in text
    # exit status / pass-fail counts
    assert "[test result: 2 passed, 1 failed]" in text
    # file edits
    assert "config.py" in text
    # dependency/setup steps
    assert "[dependency install: pip requests]" in text


def test_build_command_log_preserves_chronological_order_not_categories(tmp_path):
    """Distinct from transcript.py's grouped-by-category summary: this must
    read as an ordered log, command immediately followed by its own output,
    not commands-then-outputs-then-test-results in separate sections."""
    trajectory_path = tmp_path / "trajectory.json"
    _write_atif_trajectory(trajectory_path, _rich_trajectory_steps())

    text = build_command_log(
        trajectory_path,
        trial_name="fix-git__root",
        task_name="fix-git",
        outcome="failed",
        reward=0.0,
    )

    pip_idx = text.index("pip install requests")
    pip_output_idx = text.index("Successfully installed requests")
    sed_idx = text.index("sed -i")
    pytest_idx = text.index("pytest tests -q")

    assert pip_idx < pip_output_idx < sed_idx < pytest_idx


def test_build_command_log_never_claims_certainty_of_correctness(tmp_path):
    trajectory_path = tmp_path / "trajectory.json"
    _write_atif_trajectory(trajectory_path, _rich_trajectory_steps())

    text = build_command_log(
        trajectory_path,
        trial_name="fix-git__root",
        task_name="fix-git",
        outcome="failed",
        reward=0.0,
    )

    assert "do not repeat" not in text.lower()
    assert "definitely correct" not in text.lower()


def test_build_command_log_is_deterministic(tmp_path):
    trajectory_path = tmp_path / "trajectory.json"
    _write_atif_trajectory(trajectory_path, _rich_trajectory_steps())

    first = build_command_log(
        trajectory_path,
        trial_name="fix-git__root",
        task_name="fix-git",
        outcome="failed",
        reward=0.0,
    )
    second = build_command_log(
        trajectory_path,
        trial_name="fix-git__root",
        task_name="fix-git",
        outcome="failed",
        reward=0.0,
    )

    assert first == second


def test_build_command_log_missing_trajectory_degrades_to_header_only(tmp_path):
    text = build_command_log(
        tmp_path / "does-not-exist.json",
        trial_name="fix-git__root",
        task_name="fix-git",
        outcome="unknown",
        reward=None,
    )

    assert "fix-git" in text
    assert "outcome: unknown (reward: unknown)" in text
    assert "no commands recorded" in text


def test_build_command_log_malformed_trajectory_degrades_gracefully(tmp_path):
    trajectory_path = tmp_path / "trajectory.json"
    trajectory_path.write_text("not valid json {{{")

    text = build_command_log(
        trajectory_path,
        trial_name="fix-git__root",
        task_name="fix-git",
        outcome="unknown",
        reward=None,
    )

    assert "fix-git" in text


def test_build_command_log_truncates_to_max_chars(tmp_path):
    steps = [
        {
            "step_id": i,
            "source": "agent",
            "tool_calls": [
                {
                    "function_name": "bash_command",
                    "arguments": {"keystrokes": f"echo step-{i}\n"},
                }
            ],
            "observation": {"results": [{"content": f"output {i}"}]},
        }
        for i in range(200)
    ]
    trajectory_path = tmp_path / "trajectory.json"
    _write_atif_trajectory(trajectory_path, steps)

    text = build_command_log(
        trajectory_path,
        trial_name="fix-git__root",
        task_name="fix-git",
        outcome="failed",
        reward=0.0,
        max_chars=500,
    )

    assert len(text) <= 500
    assert "truncated" in text


def test_build_command_log_caps_commands_shown(tmp_path):
    steps = [
        {
            "step_id": i,
            "source": "agent",
            "tool_calls": [
                {
                    "function_name": "bash_command",
                    "arguments": {"keystrokes": f"echo step-{i}\n"},
                }
            ],
            "observation": {"results": [{"content": f"output {i}"}]},
        }
        for i in range(60)
    ]
    trajectory_path = tmp_path / "trajectory.json"
    _write_atif_trajectory(trajectory_path, steps)

    text = build_command_log(
        trajectory_path,
        trial_name="fix-git__root",
        task_name="fix-git",
        outcome="failed",
        reward=0.0,
        max_chars=1_000_000,
        max_commands=40,
    )

    assert "001. $ echo step-0" in text
    assert "040. $ echo step-39" in text
    assert "041. $ echo step-40" not in text
    assert "more commands not shown" in text
