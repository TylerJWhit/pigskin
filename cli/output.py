"""Output format enum, render_output(), and echo_error() for the CLI."""
from __future__ import annotations

import csv
import io
import json
import sys
from enum import Enum
from typing import Any


class OutputFormat(Enum):
    """Output format for CLI rendering."""

    TABLE = "table"
    JSON = "json"
    CSV = "csv"


def render_output(
    data: Any,
    fmt: OutputFormat,
    quiet: bool,
    verbose: bool,
) -> None:
    """Render *data* according to *fmt*.

    Rules (ADR-012 Q3):
    - TABLE + quiet  → silent (no output)
    - JSON           → always emit JSON (even if quiet=True)
    - CSV            → always emit CSV  (even if quiet=True)
    - verbose        → affects TABLE verbosity only
    """
    if fmt == OutputFormat.TABLE:
        if quiet:
            return
        # Basic table rendering — pretty-print dict/list for now
        if isinstance(data, (dict, list)):
            print(json.dumps(data, indent=2))
        else:
            print(data)

    elif fmt == OutputFormat.JSON:
        print(json.dumps(data, indent=2))

    elif fmt == OutputFormat.CSV:
        output = io.StringIO()
        if isinstance(data, dict):
            writer = csv.DictWriter(output, fieldnames=list(data.keys()))
            writer.writeheader()
            writer.writerow(data)
        elif isinstance(data, list) and data and isinstance(data[0], dict):
            writer = csv.DictWriter(output, fieldnames=list(data[0].keys()))
            writer.writeheader()
            writer.writerows(data)
        else:
            writer = csv.writer(output)
            if isinstance(data, list):
                for row in data:
                    writer.writerow(row if isinstance(row, (list, tuple)) else [row])
            else:
                writer.writerow([data])
        print(output.getvalue(), end="")


def echo_error(msg: str) -> None:
    """Print *msg* to stderr."""
    print(msg, file=sys.stderr)
