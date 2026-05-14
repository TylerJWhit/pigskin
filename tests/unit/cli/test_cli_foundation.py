"""Gate tests for #411: CLI foundation layer.

These tests define acceptance criteria for the 5 new files that the Backend
Agent will create as part of ARCH-004 Phase 0.  All tests are marked xfail
because the source files do not exist yet; they will transition to XPASS once
the implementation lands.

Files under test (none exist yet):
  cli/context.py
  cli/output.py
  cli/exceptions.py
  cli/options.py
  cli/_lazy.py
"""

from __future__ import annotations

import importlib
import io
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parents[3]
CLI_DIR = REPO_ROOT / "cli"

# ---------------------------------------------------------------------------
# AC 1 — all 5 foundation files exist
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.xfail(strict=False, reason="pending #411: cli/context.py not yet created")
def test_context_module_exists():
    """cli/context.py must exist and export AppContext."""
    import cli.context  # noqa: F401
    from cli.context import AppContext  # noqa: F401


@pytest.mark.unit
@pytest.mark.xfail(strict=False, reason="pending #411: cli/output.py not yet created")
def test_output_module_exists():
    """cli/output.py must exist and export OutputFormat and render_output."""
    import cli.output  # noqa: F401
    from cli.output import OutputFormat, render_output  # noqa: F401


@pytest.mark.unit
@pytest.mark.xfail(strict=False, reason="pending #411: cli/exceptions.py not yet created")
def test_exceptions_module_exists():
    """cli/exceptions.py must exist and export PigskinCLIError."""
    import cli.exceptions  # noqa: F401
    from cli.exceptions import PigskinCLIError  # noqa: F401


@pytest.mark.unit
@pytest.mark.xfail(strict=False, reason="pending #411: cli/options.py not yet created")
def test_options_module_exists():
    """cli/options.py must exist and export global_options."""
    import cli.options  # noqa: F401
    from cli.options import global_options  # noqa: F401


@pytest.mark.unit
@pytest.mark.xfail(strict=False, reason="pending #411: cli/_lazy.py not yet created")
def test_lazy_module_exists():
    """cli/_lazy.py must exist and export LazyGroup."""
    import cli._lazy  # noqa: F401
    from cli._lazy import LazyGroup  # noqa: F401


# ---------------------------------------------------------------------------
# AC 2 — context.py has zero Click imports
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.xfail(strict=False, reason="pending #411: cli/context.py not yet created")
def test_context_has_no_click_imports():
    """AppContext must be a plain dataclass with no Click dependency."""
    context_path = CLI_DIR / "context.py"
    assert context_path.exists(), "cli/context.py does not exist"
    source = context_path.read_text()
    assert "import click" not in source, "cli/context.py must not 'import click'"
    assert "from click" not in source, "cli/context.py must not 'from click import ...'"


# ---------------------------------------------------------------------------
# AC 3 — render_output with JSON format + quiet=True still emits JSON
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.xfail(strict=False, reason="pending #411: cli/output.py not yet created")
def test_render_output_json_quiet_still_emits():
    """JSON output must be emitted even when quiet=True (JSON is machine-readable)."""
    from cli.output import OutputFormat, render_output

    captured = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = captured
    try:
        render_output({"key": "val"}, fmt=OutputFormat.JSON, quiet=True, verbose=False)
    finally:
        sys.stdout = old_stdout

    output = captured.getvalue().strip()
    assert output, "render_output with JSON+quiet=True must still emit JSON data"
    # Ensure it is valid JSON
    import json

    parsed = json.loads(output)
    assert parsed == {"key": "val"}


# ---------------------------------------------------------------------------
# AC 4 — render_output with TABLE format + quiet=True returns nothing
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.xfail(strict=False, reason="pending #411: cli/output.py not yet created")
def test_render_output_table_quiet_is_silent():
    """TABLE output must be suppressed when quiet=True."""
    from cli.output import OutputFormat, render_output

    captured = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = captured
    try:
        result = render_output(
            {"key": "val"}, fmt=OutputFormat.TABLE, quiet=True, verbose=False
        )
    finally:
        sys.stdout = old_stdout

    output = captured.getvalue().strip()
    # Either nothing is printed, or None is returned — both signal silence
    assert not output or result is None, (
        "render_output with TABLE+quiet=True must produce no output"
    )


# ---------------------------------------------------------------------------
# AC 5 — PigskinCLIError subclass hierarchy with correct exit codes
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.xfail(strict=False, reason="pending #411: cli/exceptions.py not yet created")
def test_network_error_exit_code():
    """NetworkError must be a PigskinCLIError subclass with exit_code=3."""
    from cli.exceptions import NetworkError, PigskinCLIError

    assert issubclass(NetworkError, PigskinCLIError)
    err = NetworkError("test")
    assert err.exit_code == 3, f"Expected exit_code=3, got {err.exit_code}"


@pytest.mark.unit
@pytest.mark.xfail(strict=False, reason="pending #411: cli/exceptions.py not yet created")
def test_auth_error_exit_code():
    """AuthError must be a PigskinCLIError subclass with exit_code=4."""
    from cli.exceptions import AuthError, PigskinCLIError

    assert issubclass(AuthError, PigskinCLIError)
    err = AuthError("test")
    assert err.exit_code == 4, f"Expected exit_code=4, got {err.exit_code}"


@pytest.mark.unit
@pytest.mark.xfail(strict=False, reason="pending #411: cli/exceptions.py not yet created")
def test_lab_not_installed_error_exit_code():
    """LabNotInstalledError must be a PigskinCLIError subclass with exit_code=126."""
    from cli.exceptions import LabNotInstalledError, PigskinCLIError

    assert issubclass(LabNotInstalledError, PigskinCLIError)
    err = LabNotInstalledError("test")
    assert err.exit_code == 126, f"Expected exit_code=126, got {err.exit_code}"


@pytest.mark.unit
@pytest.mark.xfail(strict=False, reason="pending #411: cli/exceptions.py not yet created")
def test_pigskin_cli_error_is_exception():
    """PigskinCLIError must be a proper Exception subclass."""
    from cli.exceptions import PigskinCLIError

    assert issubclass(PigskinCLIError, Exception)


# ---------------------------------------------------------------------------
# AC 6 — LazyGroup: importing cli._lazy does NOT drag in the lab package
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.xfail(strict=False, reason="pending #411: cli/_lazy.py not yet created")
def test_lazy_group_import_does_not_load_lab():
    """Importing cli._lazy must NOT cause the 'lab' package to appear in sys.modules."""
    # Ensure lab is not already loaded (clean slate for this check)
    lab_keys_before = {k for k in sys.modules if k == "lab" or k.startswith("lab.")}

    # Force a fresh import of cli._lazy (unload if already cached)
    sys.modules.pop("cli._lazy", None)
    importlib.import_module("cli._lazy")

    lab_keys_after = {k for k in sys.modules if k == "lab" or k.startswith("lab.")}
    newly_loaded = lab_keys_after - lab_keys_before
    assert not newly_loaded, (
        f"Importing cli._lazy must not load lab modules; found: {newly_loaded}"
    )


@pytest.mark.unit
@pytest.mark.xfail(strict=False, reason="pending #411: cli/_lazy.py not yet created")
def test_lazy_group_is_click_group_subclass():
    """LazyGroup must subclass click.Group so Click treats it as a command group."""
    import click
    from cli._lazy import LazyGroup

    assert issubclass(LazyGroup, click.Group), (
        "LazyGroup must subclass click.Group"
    )


@pytest.mark.unit
@pytest.mark.xfail(strict=False, reason="pending #411: cli/options.py not yet created")
def test_global_options_is_callable_decorator():
    """global_options() must return a callable (decorator) for use with @global_options."""
    from cli.options import global_options

    assert callable(global_options), "global_options must be callable"
    # When called with no args it should return a decorator (another callable)
    decorator = global_options()
    assert callable(decorator), "global_options() must return a decorator"


@pytest.mark.unit
@pytest.mark.xfail(strict=False, reason="pending #411: cli/context.py not yet created")
def test_app_context_is_dataclass():
    """AppContext must be a dataclass (or similar) with at least output_format and quiet fields."""
    import dataclasses

    from cli.context import AppContext

    fields = {f.name for f in dataclasses.fields(AppContext)}
    assert "output_format" in fields or "fmt" in fields, (
        "AppContext must have an output_format (or fmt) field"
    )
    assert "quiet" in fields, "AppContext must have a quiet field"
