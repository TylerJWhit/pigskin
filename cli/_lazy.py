"""LazyGroup — a Click Group subclass that loads subcommands on demand.

Using importlib.import_module keeps heavy optional packages (e.g. ``lab``)
out of the interpreter until the user actually invokes a command from that
group.  This means ``import cli._lazy`` at the top of main.py never pulls
in the lab package.
"""
from __future__ import annotations

import importlib
from typing import Optional

import click


class LazyGroup(click.Group):
    """A :class:`click.Group` that imports subcommand modules lazily.

    Parameters
    ----------
    import_name:
        Dotted module path prefix used to resolve subcommands, e.g.
        ``"cli.commands.lab"``.  When a user runs ``pigskin lab <cmd>``,
        :meth:`get_command` calls
        ``importlib.import_module(f"{import_name}.{cmd_name}")``.
    """

    def __init__(self, *args, import_name: str = "", **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._import_name = import_name

    def get_command(self, ctx: click.Context, cmd_name: str) -> Optional[click.BaseCommand]:
        # Try the parent registry first (commands added via .add_command)
        rv = super().get_command(ctx, cmd_name)
        if rv is not None:
            return rv

        # Lazy-load via importlib — never a bare ``import lab``
        if self._import_name:
            try:
                mod = importlib.import_module(f"{self._import_name}.{cmd_name}")
                return getattr(mod, cmd_name, None)
            except ImportError:
                return None

        return None
