"""Tests for go_explore.snapshots.preflight.run_preflight_verification."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from go_explore.snapshots.preflight import (
    PreflightVerificationResult,
    run_preflight_verification,
)


def _fake_environment(tmp_path, *, exit_code=0, ctrf_summary=None, os_value="linux"):
    tests_dir = tmp_path / "task" / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test.sh").write_text("#!/bin/bash\nexit 0\n")

    environment = MagicMock()
    environment.environment_dir = tmp_path / "task" / "environment"
    environment.os = os_value
    environment.upload_dir = AsyncMock()
    environment.exec = AsyncMock(return_value=MagicMock(return_code=exit_code))

    async def fake_download_file(remote_path, local_path):
        if ctrf_summary is None:
            raise FileNotFoundError(remote_path)
        Path(local_path).write_text(json.dumps(ctrf_summary))

    environment.download_file = AsyncMock(side_effect=fake_download_file)
    return environment, tests_dir


@pytest.mark.asyncio
async def test_run_preflight_verification_happy_path(tmp_path):
    environment, _ = _fake_environment(
        tmp_path,
        exit_code=0,
        ctrf_summary={
            "results": {
                "summary": {"passed": 9, "failed": 0, "tests": 9},
                "tests": [{"name": f"test_{i}", "status": "passed"} for i in range(9)],
            }
        },
    )

    result = await run_preflight_verification(environment)

    assert result.status == "passed"
    assert result.tests_passed == 9
    assert result.tests_failed == 0
    assert result.tests_total == 9
    assert result.failing_tests == ()
    environment.upload_dir.assert_awaited_once()
    environment.exec.assert_awaited()


@pytest.mark.asyncio
async def test_run_preflight_verification_reports_failing_tests(tmp_path):
    environment, _ = _fake_environment(
        tmp_path,
        exit_code=1,
        ctrf_summary={
            "results": {
                "summary": {"passed": 9, "failed": 2, "tests": 11},
                "tests": [
                    {"name": "test_numpy_version", "status": "failed"},
                    {"name": "test_repo", "status": "failed"},
                    {"name": "test_ok", "status": "passed"},
                    {"name": "test_skipped", "status": "skipped"},
                ],
            }
        },
    )

    result = await run_preflight_verification(environment)

    assert result.status == "failed"
    assert result.tests_passed == 9
    assert result.tests_failed == 2
    assert result.tests_total == 11
    assert result.failing_tests == ("test_numpy_version", "test_repo")


@pytest.mark.asyncio
async def test_run_preflight_verification_trusts_ctrf_over_misleading_exit_code(tmp_path):
    """Regression test: test.sh conventionally ends with
    `echo ... > reward.txt`, so environment.exec's own return_code is 0 even
    when pytest failed. Observed for real in a build-cython-ext run where
    only 1 of 11 tests passed but return_code was 0 - status must be derived
    from the CTRF test counts, not the shell exit code, or the agent gets
    told 'all checks pass' while 10 of 11 are actually failing."""
    environment, _ = _fake_environment(
        tmp_path,
        exit_code=0,
        ctrf_summary={
            "results": {
                "summary": {"passed": 1, "failed": 10, "tests": 11},
                "tests": [{"name": "test_repo_cloned", "status": "passed"}]
                + [{"name": f"test_{i}", "status": "failed"} for i in range(10)],
            }
        },
    )

    result = await run_preflight_verification(environment)

    assert result.status == "failed"
    assert result.tests_passed == 1
    assert result.tests_failed == 10
    assert result.exit_code == 0


@pytest.mark.asyncio
async def test_run_preflight_verification_missing_tests_dir(tmp_path):
    environment = MagicMock()
    environment.environment_dir = tmp_path / "task" / "environment"

    result = await run_preflight_verification(environment)

    assert result.status == "unavailable"
    assert "no tests dir" in result.error


@pytest.mark.asyncio
async def test_run_preflight_verification_no_environment_dir():
    environment = MagicMock(spec=[])

    result = await run_preflight_verification(environment)

    assert result.status == "unavailable"
    assert "environment_dir" in result.error


@pytest.mark.asyncio
async def test_run_preflight_verification_non_linux_os_is_unavailable(tmp_path):
    environment, _ = _fake_environment(tmp_path, exit_code=0, os_value="windows")

    result = await run_preflight_verification(environment)

    assert result.status == "unavailable"
    assert "linux" in result.error


@pytest.mark.asyncio
async def test_run_preflight_verification_malformed_ctrf_falls_back_to_exit_code(tmp_path):
    tests_dir = tmp_path / "task" / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test.sh").write_text("#!/bin/bash\nexit 0\n")

    environment = MagicMock()
    environment.environment_dir = tmp_path / "task" / "environment"
    environment.os = "linux"
    environment.upload_dir = AsyncMock()
    environment.exec = AsyncMock(return_value=MagicMock(return_code=0))

    async def fake_download_file(remote_path, local_path):
        Path(local_path).write_text("not valid json {{{")

    environment.download_file = AsyncMock(side_effect=fake_download_file)

    result = await run_preflight_verification(environment)

    assert result.status == "passed"
    assert result.tests_passed is None
    assert result.exit_code == 0


@pytest.mark.asyncio
async def test_run_preflight_verification_upload_dir_raises(tmp_path):
    environment, _ = _fake_environment(tmp_path, exit_code=0)
    environment.upload_dir = AsyncMock(side_effect=RuntimeError("no space left"))

    result = await run_preflight_verification(environment)

    assert result.status == "unavailable"
    assert "upload_dir failed" in result.error


@pytest.mark.asyncio
async def test_run_preflight_verification_exec_raises(tmp_path):
    environment, _ = _fake_environment(tmp_path, exit_code=0)

    async def raising_exec(*args, **kwargs):
        raise RuntimeError("sandbox died")

    environment.exec = AsyncMock(side_effect=raising_exec)

    result = await run_preflight_verification(environment)

    assert result.status == "unavailable"
    assert "exec failed" in result.error


@pytest.mark.asyncio
async def test_run_preflight_verification_exec_times_out(tmp_path):
    """Covers the server-side timeout path: environment.exec itself raises a
    timeout error once the sandbox-side `timeout_sec` is exceeded."""
    environment, _ = _fake_environment(tmp_path, exit_code=0)
    environment.exec = AsyncMock(side_effect=asyncio.TimeoutError())

    result = await run_preflight_verification(environment, timeout_sec=0.05)

    assert result.status == "unavailable"
    assert "timed out" in result.error


@pytest.mark.asyncio
async def test_run_preflight_verification_never_raises_on_unexpected_error():
    """environment_dir of a type Path() can't handle must degrade to
    unavailable, not propagate - this is the top-level safety net."""
    environment = MagicMock()
    environment.environment_dir = 12345

    result = await run_preflight_verification(environment)

    assert isinstance(result, PreflightVerificationResult)
    assert result.status == "unavailable"
