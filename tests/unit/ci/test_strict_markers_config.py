"""QA Phase 1 gate tests for issue #398.

Asserts that pytest.ini is configured with --strict-markers and that all
markers defined in REQUIRED_MARKS (tests/unit/test_pytest_marks.py) are
registered in pytest.ini.

The --strict-markers test is xfail(strict=True) until the fix lands.
Marker registration tests pass immediately (unit, and all REQUIRED_MARKS,
are already registered in pytest.ini).
"""

import configparser
import pathlib

import pytest

pytestmark = pytest.mark.unit

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_PYTEST_INI = _REPO_ROOT / "pytest.ini"

# Mirrors REQUIRED_MARKS from tests/unit/test_pytest_marks.py
REQUIRED_MARKS = ["integration", "performance", "ml", "unit", "simulation", "slow"]


def _read_pytest_ini() -> configparser.ConfigParser:
    cfg = configparser.ConfigParser()
    cfg.read(_PYTEST_INI)
    return cfg


def test_strict_markers_in_addopts():
    """pytest.ini [pytest] addopts must include --strict-markers."""
    cfg = _read_pytest_ini()
    addopts = cfg.get("pytest", "addopts", fallback="")
    assert "--strict-markers" in addopts, (
        f"--strict-markers not found in pytest.ini addopts: {addopts!r}"
    )


def test_unit_marker_registered_in_pytest_ini():
    """pytest.ini must register the 'unit' marker (already present)."""
    content = _PYTEST_INI.read_text()
    assert "unit" in content, (
        "'unit' marker not found in pytest.ini markers section"
    )


@pytest.mark.parametrize("mark", REQUIRED_MARKS)
def test_required_mark_registered(mark: str):
    """Every marker in REQUIRED_MARKS must be registered in pytest.ini."""
    content = _PYTEST_INI.read_text()
    assert mark in content, (
        f"Required marker '{mark}' is not registered in pytest.ini"
    )
