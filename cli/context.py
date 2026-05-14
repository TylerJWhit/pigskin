"""CLI application context — carried via ctx.obj in every Click command."""
from __future__ import annotations

from dataclasses import dataclass, field

# IMPORTANT: Zero Click imports in this file.
from cli.output import OutputFormat


@dataclass
class AppContext:
    """Shared state threaded through all Click command invocations via ctx.obj."""

    output_format: OutputFormat = field(default=OutputFormat.TABLE)
    quiet: bool = False
    verbose: bool = False
