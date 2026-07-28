"""Tests for go_explore.snapshots.transcript.build_transcript_summary."""

from __future__ import annotations

import json
from pathlib import Path

from go_explore.snapshots.transcript import build_transcript_summary, parent_outcome


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


def test_build_transcript_summary_covers_all_required_fields(tmp_path):
    trajectory_path = tmp_path / "trajectory.json"
    _write_atif_trajectory(trajectory_path, _rich_trajectory_steps())

    text = build_transcript_summary(
        trajectory_path,
        trial_name="fix-git__root",
        task_name="fix-git",
        outcome="failed",
        reward=0.0,
    )

    assert "fix-git" in text
    assert "fix-git__root" in text
    assert "outcome: failed (reward: 0.0)" in text
    assert "pip install requests" in text
    assert "sed -i 's/toml/json/' config.py" in text
    assert "pytest tests -q" in text
    assert "config.py" in text  # file touched, from the sed command heuristic
    assert "2 passed, 1 failed" in text  # observed test counts
    assert "pip: requests" in text  # dependency install
    assert "FAILED test_parser.py::test_toml_config" in text  # last observation


def test_build_transcript_summary_never_claims_certainty_of_correctness(tmp_path):
    """The prompt-contract discipline from T008 section 4: the transcript must
    not read as proof the parent was correct, and must not tell the child to
    avoid repeating the parent's approach."""
    trajectory_path = tmp_path / "trajectory.json"
    _write_atif_trajectory(trajectory_path, _rich_trajectory_steps())

    text = build_transcript_summary(
        trajectory_path,
        trial_name="fix-git__root",
        task_name="fix-git",
        outcome="failed",
        reward=0.0,
    )

    assert "do not repeat" not in text.lower()
    assert "correct" not in text.lower()


def test_build_transcript_summary_is_deterministic(tmp_path):
    trajectory_path = tmp_path / "trajectory.json"
    _write_atif_trajectory(trajectory_path, _rich_trajectory_steps())

    first = build_transcript_summary(
        trajectory_path,
        trial_name="fix-git__root",
        task_name="fix-git",
        outcome="failed",
        reward=0.0,
    )
    second = build_transcript_summary(
        trajectory_path,
        trial_name="fix-git__root",
        task_name="fix-git",
        outcome="failed",
        reward=0.0,
    )

    assert first == second


def test_build_transcript_summary_missing_trajectory_degrades_to_header_only(tmp_path):
    text = build_transcript_summary(
        tmp_path / "does-not-exist.json",
        trial_name="fix-git__root",
        task_name="fix-git",
        outcome="unknown",
        reward=None,
    )

    assert "fix-git" in text
    assert "outcome: unknown (reward: unknown)" in text


def test_build_transcript_summary_malformed_trajectory_degrades_gracefully(tmp_path):
    trajectory_path = tmp_path / "trajectory.json"
    trajectory_path.write_text("not valid json {{{")

    text = build_transcript_summary(
        trajectory_path,
        trial_name="fix-git__root",
        task_name="fix-git",
        outcome="unknown",
        reward=None,
    )

    assert "fix-git" in text


def test_build_transcript_summary_truncates_to_max_chars(tmp_path):
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

    text = build_transcript_summary(
        trajectory_path,
        trial_name="fix-git__root",
        task_name="fix-git",
        outcome="failed",
        reward=0.0,
        max_chars=500,
    )

    assert len(text) <= 500
    assert "truncated" in text


def test_build_transcript_summary_caps_commands_shown(tmp_path):
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

    text = build_transcript_summary(
        trajectory_path,
        trial_name="fix-git__root",
        task_name="fix-git",
        outcome="failed",
        reward=0.0,
        max_chars=1_000_000,
    )

    assert "echo step-0" in text
    assert "more commands not shown" in text


def test_parent_outcome_classifies_solved_failed_timed_out_unknown():
    assert parent_outcome(1.0, None) == "solved"
    assert parent_outcome(0.0, None) == "failed"
    assert parent_outcome(None, None) == "unknown"
    assert parent_outcome(None, "TimeoutError") == "timed_out"
    assert parent_outcome(0.0, "TimeoutError") == "timed_out"
