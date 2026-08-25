"""Enforce docstring style for robot_drivers."""

from ament_pep257.main import main
import pytest


@pytest.mark.linter
@pytest.mark.pep257
def test_pep257() -> None:
    """Run pep257 for package and tests."""
    ignored = ["D204", "D213", "D401", "D403", "D406", "D407", "D413"]
    assert main(argv=["--add-ignore", *ignored, "robot_drivers", "test"]) == 0
