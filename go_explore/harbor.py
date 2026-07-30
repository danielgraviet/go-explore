from __future__ import annotations

import os
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class HarborRunConfig:
    """Configuration for one Harbor job invocation."""

    jobs_dir: Path = Path("jobs")
    agent: str | None = "oracle"
    agent_import_path: str | None = None
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
        if self.agent is not None and self.agent_import_path is not None:
            raise ValueError("Set only one of agent or agent_import_path.")
        if self.n_attempts < 1:
            raise ValueError("n_attempts must be >= 1.")
        if self.n_concurrent < 1:
            raise ValueError("n_concurrent must be >= 1.")


def build_harbor_command(config: HarborRunConfig) -> list[str]:
    config.validate()

    cmd = ["harbor", "run"]

    if config.agent is not None:
        cmd.extend(["--agent", config.agent])
    if config.agent_import_path is not None:
        cmd.extend(["--agent-import-path", config.agent_import_path])

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
        cmd.extend(["--include-task-name", config.task_name])
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

    return subprocess.run(
        cmd,
        check=False,
        text=True,
        env=environment_with_repo_path(),
    )


def with_agent_kwarg(
    extra_args: Sequence[str],
    key: str,
    value: str,
) -> tuple[str, ...]:
    """Return `extra_args` with exactly one `--ak key=value`, replacing any
    prior value for `key`.

    `--ak` is Harbor's agent-kwarg flag; the snapshot-aware agent factories
    read these as constructor kwargs (see `go_explore/agents/factory.py`).
    """

    cleaned: list[str] = []
    index = 0
    while index < len(extra_args):
        current = extra_args[index]
        if current == "--ak" and index + 1 < len(extra_args):
            if str(extra_args[index + 1]).split("=", 1)[0] == key:
                index += 2
                continue
            cleaned.extend([current, extra_args[index + 1]])
            index += 2
            continue
        cleaned.append(current)
        index += 1

    cleaned.extend(["--ak", f"{key}={value}"])
    return tuple(cleaned)


def environment_with_repo_path(base: dict[str, str] | None = None) -> dict[str, str]:
    """Make local agent imports available to Harbor's separate process."""

    environment = dict(base or os.environ)
    repo_root = str(Path(__file__).resolve().parent.parent)
    current = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = os.pathsep.join(
        [repo_root] + ([current] if current else [])
    )
    return environment
