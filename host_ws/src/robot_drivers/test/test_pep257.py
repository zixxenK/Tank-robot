"""Enforce docstring style for robot_drivers."""

from ament_pep257.main import main
import pytest


@pytest.mark.linter
@pytest.mark.pep257
def test_pep257() -> None:
    """Run pep257 for package and tests."""
    assert main(argv=["robot_drivers", "test"]) == 0
