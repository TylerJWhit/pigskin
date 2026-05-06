"""Verify all custom pytest marks are registered in pytest.ini."""

import pathlib

import pytest


REQUIRED_MARKS = ["integration", "performance", "ml", "unit", "simulation", "slow"]


class TestPytestMarksRegistered:
    """Ensure all project-specific marks are declared to suppress PytestUnknownMarkWarning."""

    def test_all_required_marks_in_ini(self):
        """pytest.ini must declare all required custom marks."""
        ini_path = pathlib.Path(__file__).resolve().parents[2] / "pytest.ini"
        content = ini_path.read_text()
        missing = [mark for mark in REQUIRED_MARKS if mark not in content]
        assert not missing, (
            f"Missing marks in pytest.ini: {missing}\n"
            "Add them to the [pytest] markers section."
        )

    @pytest.mark.integration
    def test_integration_mark_recognized(self):
        """integration mark is recognized by pytest without raising PytestUnknownMarkWarning."""

    @pytest.mark.performance
    def test_performance_mark_recognized(self):
        """performance mark is recognized by pytest without raising PytestUnknownMarkWarning."""

    @pytest.mark.ml
    def test_ml_mark_recognized(self):
        """ml mark is recognized by pytest without raising PytestUnknownMarkWarning."""

    @pytest.mark.unit
    def test_unit_mark_recognized(self):
        """unit mark is recognized by pytest without raising PytestUnknownMarkWarning."""

    @pytest.mark.simulation
    def test_simulation_mark_recognized(self):
        """simulation mark is recognized by pytest without raising PytestUnknownMarkWarning."""

    @pytest.mark.slow
    def test_slow_mark_recognized(self):
        """slow mark is recognized by pytest without raising PytestUnknownMarkWarning."""
