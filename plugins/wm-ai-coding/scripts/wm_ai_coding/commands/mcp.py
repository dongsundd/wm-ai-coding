"""Parse MCP invocations and report launch failures without touching server streams."""
from __future__ import annotations

import argparse
import sys

from ..integrations.mcp import SUPPORTED, launch


class _ServerArguments(argparse.Action):
    """Parse the server and its tail together so argparse preserves a leading --."""

    def __call__(self, parser, namespace, values, option_string=None):
        if not values:
            parser.error("MCP server is required")
        if values[0] not in SUPPORTED:
            parser.error(f"unsupported MCP server: {values[0]}")
        namespace.server = values[0]
        namespace.args = values[1:]


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("server", nargs=argparse.REMAINDER, action=_ServerArguments,
                        help="MCP server (" + ", ".join(sorted(SUPPORTED)) + "); remaining arguments are forwarded unchanged")


def run(args: argparse.Namespace) -> int:
    try:
        return launch(args.server, args.args)
    except OSError as exc:
        print(str(exc), file=sys.stderr)
        return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wm mcp")
    add_arguments(parser)
    return run(parser.parse_args(argv))
