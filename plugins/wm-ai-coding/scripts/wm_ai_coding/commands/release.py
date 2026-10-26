"""Release command adapter."""
import argparse
import json
from pathlib import Path
from ..infrastructure.paths import plugin_root
from ..infrastructure.release import build, verify, package


def add_arguments(parser: argparse.ArgumentParser) -> None:
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("build")
    package_parser = commands.add_parser('package')
    package_parser.add_argument('--host', choices=['codex','claude','opencode'], required=True)
    package_parser.add_argument('--output', type=Path, required=True)
    verify_parser = commands.add_parser("verify")
    verify_parser.add_argument("--mcp", action="store_true")


def run(args: argparse.Namespace) -> int:
    root = plugin_root()
    if args.action == 'package':
        print(json.dumps(package(root, args.host, args.output)))
        return 0
    if args.action == "build":
        result = build(root)
        print(json.dumps({k: v for k, v in result.items() if k != "files"}))
        return 0
    result = verify(root, mcp=args.mcp)
    print(json.dumps(result, indent=2))
    return 0 if result["valid"] else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wm release")
    add_arguments(parser)
    return run(parser.parse_args(argv))
