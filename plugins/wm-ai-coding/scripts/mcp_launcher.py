"""Resolve globally installed MCP binaries without platform-specific manifest names."""
from __future__ import annotations

import shutil
import subprocess
import sys


def main():
    name = sys.argv[1]
    if name not in {"codegraph", "playwright-mcp"}:
        raise SystemExit("unsupported MCP server")
    command = shutil.which(name) or shutil.which(name + ".cmd")
    if not command:
        raise SystemExit(f"{name} is not installed; run dependency_preflight.py for diagnostics")
    raise SystemExit(subprocess.call([command, *sys.argv[2:]]))


if __name__ == "__main__":
    main()
