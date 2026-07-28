"""Tests for go_explore.snapshots.diff_only.apply_parent_diff."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from go_explore.snapshots.diff_only import (
    DIFF_UPLOAD_TARGET,
    apply_parent_diff,
)


def _fake_environment(*, exit_code=0, stderr="", stdout="", workdir="/app"):
    environment = MagicMock()
    environment.upload_file = AsyncMock()
    environment.exec = AsyncMock(
        return_value=MagicMock(return_code=exit_code, stderr=stderr, stdout=stdout)
    )
    environment.task_env_config = MagicMock(workdir=workdir)
    return environment


@pytest.mark.asyncio
async def test_apply_parent_diff_happy_path(tmp_path):
    diff_path = tmp_path / "parent.diff"
    diff_path.write_text("diff --git a/x b/x\n--- a/x\n+++ b/x\n")
    environment = _fake_environment(exit_code=0)

    result = await apply_parent_diff(environment, diff_path)

    assert result.status == "applied"
    assert result.exit_code == 0
    environment.upload_file.assert_awaited_once_with(
        source_path=diff_path, target_path=DIFF_UPLOAD_TARGET
    )
    exec_call = environment.exec.await_args.kwargs
    assert exec_call["cwd"] == "/app"
    assert "git apply" in exec_call["command"]
    assert DIFF_UPLOAD_TARGET in exec_call["command"]


@pytest.mark.asyncio
async def test_apply_parent_diff_reports_git_apply_failure(tmp_path):
    diff_path = tmp_path / "parent.diff"
    diff_path.write_text("diff --git a/x b/x\n--- a/x\n+++ b/x\n")
    environment = _fake_environment(exit_code=1, stderr="patch does not apply")

    result = await apply_parent_diff(environment, diff_path)

    assert result.status == "failed"
    assert result.exit_code == 1
    assert "patch does not apply" in result.detail


@pytest.mark.asyncio
async def test_apply_parent_diff_missing_artifact(tmp_path):
    diff_path = tmp_path / "missing.diff"
    environment = _fake_environment()

    result = await apply_parent_diff(environment, diff_path)

    assert result.status == "failed"
    assert "no diff artifact" in result.detail
    environment.upload_file.assert_not_awaited()


@pytest.mark.asyncio
async def test_apply_parent_diff_empty_diff_is_trivially_applied(tmp_path):
    diff_path = tmp_path / "parent.diff"
    diff_path.write_text("   \n")
    environment = _fake_environment()

    result = await apply_parent_diff(environment, diff_path)

    assert result.status == "applied"
    environment.upload_file.assert_not_awaited()


@pytest.mark.asyncio
async def test_apply_parent_diff_missing_exec_hook(tmp_path):
    diff_path = tmp_path / "parent.diff"
    diff_path.write_text("diff --git a/x b/x\n")
    environment = MagicMock(spec=["upload_file"])
    environment.upload_file = AsyncMock()

    result = await apply_parent_diff(environment, diff_path)

    assert result.status == "failed"
    assert "upload_file/exec" in result.detail


@pytest.mark.asyncio
async def test_apply_parent_diff_upload_raises(tmp_path):
    diff_path = tmp_path / "parent.diff"
    diff_path.write_text("diff --git a/x b/x\n")
    environment = _fake_environment()
    environment.upload_file = AsyncMock(side_effect=RuntimeError("no space left"))

    result = await apply_parent_diff(environment, diff_path)

    assert result.status == "failed"
    assert "upload_file failed" in result.detail


@pytest.mark.asyncio
async def test_apply_parent_diff_exec_raises(tmp_path):
    diff_path = tmp_path / "parent.diff"
    diff_path.write_text("diff --git a/x b/x\n")
    environment = _fake_environment()
    environment.exec = AsyncMock(side_effect=RuntimeError("sandbox died"))

    result = await apply_parent_diff(environment, diff_path)

    assert result.status == "failed"
    assert "exec failed" in result.detail
