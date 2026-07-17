from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path
from uuid import uuid4

from go_explore.harbor import HarborRunConfig, build_harbor_command
from go_explore.results import summarize_job


def _load_env_file(path: Path) -> dict[str, str]:
    env = os.environ.copy()
    project_root = str(Path.cwd())
    pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        f"{project_root}{os.pathsep}{pythonpath}" if pythonpath else project_root
    )
    if not path.exists():
        return env

    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key] = value.strip().strip('"').strip("'")

    return env


def _format_command(cmd: list[str]) -> str:
    lines = ["", "Harbor Daytona agent command", "=" * 28]
    lines.append(shlex.join(cmd))
    lines.append("")
    lines.append("Multiline form")
    lines.append("-" * 14)

    rendered = ["harbor run \\"]
    for index in range(2, len(cmd), 2):
        chunk = cmd[index : index + 2]
        if not chunk:
            continue
        rendered.append(f"  {shlex.join(chunk)} \\")
    rendered[-1] = rendered[-1].removesuffix(" \\")
    lines.extend(rendered)
    return "\n".join(lines)


def test_daytona_terminus2_claude_agent_runs_fix_git_successfully(capsys):
    job_name = f"e2e-daytona-agent-{uuid4().hex[:8]}"
    config = HarborRunConfig(
        agent="terminus-2",
        model="anthropic/claude-haiku-4-5-20251001",
        env="daytona",
        jobs_dir=Path("jobs"),
        n_attempts=1,
        n_concurrent=1,
        dataset="terminal-bench@2.0",
        task_name="fix-git",
        job_name=job_name,
        export_traces=True,
    )

    cmd = build_harbor_command(config)

    with capsys.disabled():
        print(_format_command(cmd))

    assert cmd == [
        "harbor",
        "run",
        "--agent",
        "terminus-2",
        "--env",
        "daytona",
        "--jobs-dir",
        "jobs",
        "--n-attempts",
        "1",
        "--n-concurrent",
        "1",
        "--dataset",
        "terminal-bench@2.0",
        "--model",
        "anthropic/claude-haiku-4-5-20251001",
        "--include-task-name",
        "fix-git",
        "--job-name",
        job_name,
        "--export-traces",
    ]

    result = subprocess.run(
        cmd,
        check=False,
        capture_output=True,
        text=True,
        env=_load_env_file(Path(".env")),
    )

    with capsys.disabled():
        print("")
        print("Harbor stdout")
        print("=" * 13)
        print(result.stdout or "<empty>")
        print("")
        print("Harbor stderr")
        print("=" * 13)
        print(result.stderr or "<empty>")

    assert result.returncode == 0

    summary = summarize_job(Path("jobs") / job_name)

    with capsys.disabled():
        print("")
        print("Parsed job summary")
        print("=" * 18)
        print(f"job_dir: {summary.job_dir}")
        print(f"trials: {len(summary.trials)}/{summary.n_total_trials}")
        print(f"errors: {summary.n_errors}")
        print(f"mean: {summary.mean}")
        for trial in summary.trials:
            print(
                f"- {trial.trial_name}: "
                f"reward={trial.reward} "
                f"exception={trial.exception_type}"
            )

    assert summary.n_total_trials == 1
    assert summary.n_errors == 0
    assert summary.mean == 1.0
    assert len(summary.trials) == 1
    assert summary.trials[0].succeeded

    trial_dir = Path("jobs") / job_name / summary.trials[0].trial_name
    assert (trial_dir / "agent" / "trajectory.json").exists()
    assert (trial_dir / "verifier" / "reward.txt").read_text().strip() == "1"
