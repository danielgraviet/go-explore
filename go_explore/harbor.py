from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class HarborRunConfig:
    """Configuration for one Harbor job invocation."""

    jobs_dir: Path = Path("jobs")
    agent: str | None = "oracle"
    env: str = "docker"
    dataset: str | None = None
    path: Path | None = None
    model: str | None = None
    task_name: str | None = None
    n_tasks: int | None = None
    n_attempts: int = 1
    n_concurrent: int = 1
    job_name: str | None = None
    export_traces: bool = True
    environment_kwargs: tuple[str, ...] = field(default_factory=tuple)
    extra_args: tuple[str, ...] = field(default_factory=tuple)

    def validate(self) -> None:
        if bool(self.dataset) == bool(self.path):
            raise ValueError("Set exactly one of dataset or path.")
        if self.n_attempts < 1:
            raise ValueError("n_attempts must be >= 1.")
        if self.n_concurrent < 1:
            raise ValueError("n_concurrent must be >= 1.")


def build_harbor_command(config: HarborRunConfig) -> list[str]:
    config.validate()

    cmd = ["harbor", "run"]

    if config.agent is not None:
        cmd.extend(["--agent", config.agent])

    cmd.extend(
        [
            "--env",
            config.env,
            "--jobs-dir",
            str(config.jobs_dir),
            "--n-attempts",
            str(config.n_attempts),
            "--n-concurrent",
            str(config.n_concurrent),
        ]
    )

    if config.dataset:
        cmd.extend(["--dataset", config.dataset])
    if config.path:
        cmd.extend(["--path", str(config.path)])
    if config.model:
        cmd.extend(["--model", config.model])
    if config.task_name:
        cmd.extend(["--task-name", config.task_name])
    if config.n_tasks is not None:
        cmd.extend(["--n-tasks", str(config.n_tasks)])
    if config.job_name:
        cmd.extend(["--job-name", config.job_name])
    if config.export_traces:
        cmd.append("--export-traces")
    for environment_kwarg in config.environment_kwargs:
        cmd.extend(["--ek", environment_kwarg])

    cmd.extend(config.extra_args)
    return cmd


def run_harbor(config: HarborRunConfig, *, dry_run: bool = False) -> subprocess.CompletedProcess[str] | list[str]:
    cmd = build_harbor_command(config)
    if dry_run:
        return cmd

    return subprocess.run(cmd, check=False, text=True)
