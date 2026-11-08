"""Suite-wide pytest options and fixtures."""

from pathlib import Path

import pytest

from tests.golden import UPDATE_OPTION, AssertGolden, check_golden

pytest_plugins = ["tests.samples"]


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(UPDATE_OPTION, action="store_true", help="rewrite golden files from the current output")


@pytest.fixture
def assert_golden(pytestconfig: pytest.Config) -> AssertGolden:
    """Compare output with its golden, or rewrite the golden under ``--update-goldens``."""
    update = bool(pytestconfig.getoption(UPDATE_OPTION))

    def compare(actual: str, path: Path) -> None:
        check_golden(actual, path, update=update)

    return compare
