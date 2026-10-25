"""Dispatch the public CLI without intercepting tool arguments or streams."""
from __future__ import annotations
from .commands import workflow


def main(argv: list[str] | None = None) -> int:
    args = workflow.parser(include_tools=True).parse_args(argv)
    handler = getattr(args, "handler", None)
    return handler(args) if handler else workflow.execute(args)
