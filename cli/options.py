"""Shared Click option decorators for the Pigskin CLI."""
from __future__ import annotations

from typing import Callable

import click


def global_options() -> Callable:
    """Return a decorator that adds shared CLI flags to a Click command.

    Flags added:
    - ``--output / -o``  (choice: table, json, csv; default: table)
    - ``--quiet  / -q``  (flag, default False)
    - ``--verbose / -v`` (flag, default False)

    Usage::

        @cli.command()
        @global_options()
        def my_command(output, quiet, verbose, **kwargs):
            ...
    """

    def decorator(func: Callable) -> Callable:
        func = click.option(
            "--output", "-o",
            type=click.Choice(["table", "json", "csv"], case_sensitive=False),
            default="table",
            show_default=True,
            help="Output format.",
        )(func)
        func = click.option(
            "--quiet", "-q",
            is_flag=True,
            default=False,
            help="Suppress non-essential output.",
        )(func)
        func = click.option(
            "--verbose", "-v",
            is_flag=True,
            default=False,
            help="Enable verbose output.",
        )(func)
        return func

    return decorator
