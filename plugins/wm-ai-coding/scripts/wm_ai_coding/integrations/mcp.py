"""Resolve and launch globally installed MCP servers, inheriting protocol streams."""
from __future__ import annotations

import shutil
import subprocess
from collections.abc import Sequence


SUPPORTED = {"codegraph", "playwright-mcp"}


def launch(server: str, args: Sequence[str]) -> int:
    if server not in SUPPORTED:
        raise ValueError(f"unsupported MCP server: {server}")
    command = shutil.which(server) or shutil.which(server + ".cmd")
    if not command:
        raise FileNotFoundError(f"{server} is not installed; run wm preflight for diagnostics")
    return subprocess.call([command, *args])
