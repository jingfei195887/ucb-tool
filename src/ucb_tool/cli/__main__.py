from __future__ import annotations

import sys

import click

from ucb_tool.cli.commands import (
    apply_xlsx_cmd,
    diff_cmd,
    export_ucb_cmd,
    export_xlsx_cmd,
    set_cmd,
    show_cmd,
    validate_cmd,
)


@click.group()
@click.version_option(package_name="ucb-tool")
def main() -> None:
    """ucb-tool — Infineon AURIX UCB hex editor."""


main.add_command(show_cmd)
main.add_command(set_cmd)
main.add_command(validate_cmd)
main.add_command(export_xlsx_cmd)
main.add_command(apply_xlsx_cmd)
main.add_command(diff_cmd)
main.add_command(export_ucb_cmd)


if __name__ == "__main__":
    sys.exit(main())
