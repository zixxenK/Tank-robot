"""Enforce Python style for robot_drivers."""

from ament_flake8.main import main_with_errors
import pytest


@pytest.mark.flake8
@pytest.mark.linter
def test_flake8() -> None:
    """Run flake8 with the repository line-length policy."""
    result, errors = main_with_errors(argv=["--linelength", "99"])
    assert result == 0, "\n".join(errors)
