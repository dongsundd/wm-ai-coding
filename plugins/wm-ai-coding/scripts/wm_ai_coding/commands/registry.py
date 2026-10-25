"""Register each tool's real arguments and handler from one command list."""
from importlib import import_module

TOOLS = {
    "hook": "Host event bridge",
    "mcp": "MCP server launcher",
    "release": "Build or verify releases",
    "preflight": "Dependency diagnostics",
}


def register(subparsers) -> None:
    for name, description in TOOLS.items():
        command = import_module(f"{__package__}.{name}")
        parser = subparsers.add_parser(name, help=description)
        command.add_arguments(parser)
        parser.set_defaults(handler=command.run)
