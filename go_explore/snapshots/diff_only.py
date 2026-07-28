from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

DIFF_UPLOAD_TARGET = "/tmp/go_explore_parent.diff"


class DiffApplyFailed(RuntimeError):
    """Raised when a `diff_only` child's parent diff does not apply cleanly.

    A distinct exception type (rather than reusing a generic RuntimeError) so
    downstream analysis can separate this executor failure from an ordinary
    task failure (agent ran to completion, reward < 1, no exception).
    """


@dataclass(frozen=True)
class DiffApplyResult:
    """Outcome of attempting to apply one parent diff artifact."""

    status: Literal["applied", "failed"]
    exit_code: int | None = None
    detail: str | None = None


async def apply_parent_diff(
    environment: Any,
    diff_path: Path | str,
    *,
    timeout_sec: float = 60.0,
) -> DiffApplyResult:
    """Apply `diff_path` (a parent `git diff` artifact) onto `environment`'s
    checkout via `git apply`.

    Returns a result rather than raising so callers can decide how to report
    an executor failure - `SnapshotAwareAgent.setup` turns a non-"applied"
    result into `DiffApplyFailed`.
    """
    diff_path = Path(diff_path)
    if not diff_path.is_file():
        return DiffApplyResult(status="failed", detail=f"no diff artifact at {diff_path}")

    diff_text = diff_path.read_text()
    if not diff_text.strip():
        return DiffApplyResult(
            status="applied", exit_code=0, detail="empty diff, nothing to apply"
        )

    upload_file = getattr(environment, "upload_file", None)
    exec_fn = getattr(environment, "exec", None)
    if upload_file is None or exec_fn is None:
        return DiffApplyResult(
            status="failed", detail="environment has no upload_file/exec"
        )

    try:
        await upload_file(source_path=diff_path, target_path=DIFF_UPLOAD_TARGET)
    except Exception as error:  # noqa: BLE001
        return DiffApplyResult(status="failed", detail=f"upload_file failed: {error}")

    workdir = _repo_workdir(environment)
    try:
        result = await exec_fn(
            command=f"git apply --whitespace=nowarn {DIFF_UPLOAD_TARGET}",
            cwd=workdir,
            timeout_sec=int(timeout_sec),
        )
    except Exception as error:  # noqa: BLE001
        return DiffApplyResult(status="failed", detail=f"exec failed: {error}")

    exit_code = getattr(result, "return_code", None)
    if exit_code is None:
        exit_code = getattr(result, "exit_code", None)

    if exit_code == 0:
        return DiffApplyResult(status="applied", exit_code=exit_code)

    stderr = (getattr(result, "stderr", "") or "").strip()
    stdout = (getattr(result, "stdout", "") or "").strip()
    detail = stderr or stdout or f"git apply exited {exit_code}"
    return DiffApplyResult(status="failed", exit_code=exit_code, detail=detail)


def _repo_workdir(environment: Any) -> str | None:
    task_env_config = getattr(environment, "task_env_config", None)
    workdir = getattr(task_env_config, "workdir", None)
    return str(workdir) if workdir else None
