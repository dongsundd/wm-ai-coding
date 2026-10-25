"""Dependency command adapter."""
import argparse
import json
from pathlib import Path
from ..integrations.dependencies import inspect_dependencies


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--install", action="store_true", help="globally install only missing MCP packages")
    parser.add_argument("--project", type=Path, help="check a project's local CodeGraph index")
    parser.add_argument("--init-project", action="store_true", help="initialize a missing project index")
    parser.add_argument("--json", action="store_true", help="emit JSON")


def run(args: argparse.Namespace) -> int:
    payload = inspect_dependencies(install=args.install, project=args.project, initialize_project=args.init_project)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for check in payload["checks"]:
            print(f"{'OK' if check['available'] else 'MISSING'} {check['name']}: {check['detail']}")
        for result in payload["install_results"]:
            print(f"{'INSTALLED' if result['available'] else 'FAILED'} {result['name']}: {result['detail']}")
    return 0 if payload["ok"] else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wm preflight", description="Check wm-ai-coding dependencies")
    add_arguments(parser)
    return run(parser.parse_args(argv))
