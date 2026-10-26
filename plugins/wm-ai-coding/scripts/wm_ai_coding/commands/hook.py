"""Parse hook invocations and translate JSON streams at the CLI boundary."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from ..integrations.hook_bridge import dispatch, failure
from ..integrations.hooks import CAPABILITIES


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("host", choices=sorted(CAPABILITIES))
    parser.add_argument("event")


def run(args: argparse.Namespace) -> int:
    try:
        payload = json.load(sys.stdin)
        result = dispatch(args.host, args.event, payload, repo=getattr(args, "repo", None))
    except Exception as exc:
        # Hook execution failures must remain valid host protocol responses.
        result = failure(args.host, args.event, exc)
    print(json.dumps(result, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wm hook")
    parser.add_argument("--repo", type=Path)
    add_arguments(parser)
    return run(parser.parse_args(argv))
