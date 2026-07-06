from __future__ import annotations

from pathlib import Path

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-e2e",
        action="store_true",
        default=False,
        help="Run e2e tests that invoke Harbor, Docker, Daytona, or model APIs.",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    run_e2e = bool(config.getoption("--run-e2e"))
    keyword_expr = str(config.option.keyword or "")
    e2e_requested = run_e2e or "e2e" in keyword_expr
    skip_e2e = pytest.mark.skip(
        reason="e2e test skipped by default; use --run-e2e or -k e2e to run it"
    )

    for item in items:
        if _is_e2e_item(item):
            item.add_marker("e2e")
            if not e2e_requested:
                item.add_marker(skip_e2e)


def _is_e2e_item(item: pytest.Item) -> bool:
    try:
        path = Path(str(item.path))
    except TypeError:
        return False

    return "e2e" in path.parts
