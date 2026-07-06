from __future__ import annotations

import os
import shlex
import subprocess
from uuid import uuid4
from pathlib import Path

from go_explore.harbor import HarborRunConfig, build_harbor_command
from go_explore.results import summarize_job


def _load_env_file(path: Path) -> dict[str, str]:
    env = os.environ.copy()
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
    lines = ["", "Harbor oracle smoke command", "=" * 27]
    lines.append(shlex.join(cmd))
    lines.append("")
    lines.append("Multiline form")
    lines.append("-" * 14)

    chunks = [
        cmd[:2],
        cmd[2:4],
        cmd[4:6],
        cmd[6:8],
        cmd[8:10],
        cmd[10:12],
        cmd[12:14],
        cmd[14:16],
        cmd[16:18],
        cmd[18:20],
        cmd[20:],
    ]
    rendered = ["harbor run \\"]
    for chunk in chunks[1:]:
        if not chunk:
            continue
        rendered.append(f"  {shlex.join(chunk)} \\")
    rendered[-1] = rendered[-1].removesuffix(" \\")
    lines.extend(rendered)
    return "\n".join(lines)


def test_docker_oracle_harbor_command_runs_successfully(capsys):
    job_name = f"e2e-docker-oracle-{uuid4().hex[:8]}"
    config = HarborRunConfig(
        agent="oracle",
        jobs_dir=Path("jobs"),
        n_attempts=1,
        n_concurrent=1,
        dataset="terminal-bench-sample@2.0",
        n_tasks=1,
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
        "oracle",
        "--env",
        "docker",
        "--jobs-dir",
        "jobs",
        "--n-attempts",
        "1",
        "--n-concurrent",
        "1",
        "--dataset",
        "terminal-bench-sample@2.0",
        "--n-tasks",
        "1",
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
