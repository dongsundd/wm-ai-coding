#!/usr/bin/env python3
"""Prefer global MCP commands and optionally install only missing dependencies."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path


DEPENDENCIES = (
    ("codegraph", "codegraph", "@colbymchenry/codegraph"),
    ("playwright", "playwright-mcp", "@playwright/mcp@0.0.83"),
)


@dataclass
class Check:
    name: str
    available: bool
    detail: str


def locate(name: str) -> Check:
    path = (shutil.which(name) or shutil.which(name + ".cmd"))
    return Check(name, path is not None, path or "not found on PATH")


def probe(name: str) -> Check:
    """Require the command to exist and start successfully, not merely be on PATH."""
    path = (shutil.which(name) or shutil.which(name + ".cmd"))
    if not path:
        return Check(name, False, "not found on PATH")
    try:
        result = subprocess.run(
            [path, "--help"], capture_output=True, text=True, timeout=30, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return Check(name, False, str(exc))
    output = (result.stdout or result.stderr).strip().splitlines()
    detail = output[-1] if output else path
    if result.returncode != 0:
        detail = f"unusable (exit {result.returncode}): {detail}"
    return Check(name, result.returncode == 0, detail)


def version(name: str) -> Check:
    path = (shutil.which(name) or shutil.which(name + ".cmd"))
    if not path:
        return Check(name, False, "not found on PATH")
    try:
        result = subprocess.run(
            [path, "--version"], capture_output=True, text=True, timeout=20, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return Check(name, False, str(exc))
    detail = (result.stdout or result.stderr).strip()
    return Check(name, result.returncode == 0, detail or path)


def install_global(npm: str, label: str, package: str) -> Check:
    try:
        result = subprocess.run(
            [npm, "install", "--global", package],
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return Check(label, False, str(exc))
    output = (result.stdout or result.stderr).strip().splitlines()
    detail = output[-1] if output else f"exit {result.returncode}"
    return Check(label, result.returncode == 0, detail)


def project_index(command: str, project: Path, initialize: bool) -> tuple[Check, Check | None]:
    index_dir = project / ".codegraph"
    init_result: Check | None = None
    if initialize and not index_dir.is_dir():
        result = subprocess.run(
            [command, "init"], cwd=project, capture_output=True, text=True,
            timeout=900, check=False,
        )
        output = (result.stdout or result.stderr).strip().splitlines()
        detail = output[-1] if output else f"exit {result.returncode}"
        init_result = Check("codegraph-init", result.returncode == 0, detail)
    if not index_dir.is_dir():
        return Check("codegraph-index", False, f"missing: {index_dir}"), init_result
    result = subprocess.run(
        [command, "status"], cwd=project, capture_output=True, text=True,
        timeout=60, check=False,
    )
    output = (result.stdout or result.stderr).strip().splitlines()
    detail = output[-1] if output else str(index_dir)
    return Check("codegraph-index", result.returncode == 0, detail), init_result


def main() -> int:
    parser = argparse.ArgumentParser(description="Check wm-ai-coding dependencies")
    parser.add_argument("--install", action="store_true", help="globally install only missing MCP packages")
    parser.add_argument("--project", type=Path, help="check a project's local CodeGraph index")
    parser.add_argument("--init-project", action="store_true", help="initialize a missing project index")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    args = parser.parse_args()

    checks = [version(name) for name in ("node", "npm")]
    base_ok = all(check.available for check in checks)
    before = {command: probe(command) for _, command, _ in DEPENDENCIES}
    install_results: list[Check] = []

    if args.install and base_ok:
        npm = shutil.which("npm")
        assert npm is not None
        for label, command, package in DEPENDENCIES:
            if not before[command].available:
                install_results.append(install_global(npm, label, package))

    after = [probe(command) for _, command, _ in DEPENDENCIES]
    checks.extend(after)
    project_result: Check | None = None
    init_result: Check | None = None
    if args.project:
        project = args.project.resolve()
        codegraph = (shutil.which("codegraph") or shutil.which("codegraph.cmd"))
        if codegraph and next(check for check in after if check.name == "codegraph").available:
            project_result, init_result = project_index(codegraph, project, args.init_project)
        else:
            project_result = Check("codegraph-index", False, "CodeGraph CLI is unavailable")
        checks.append(project_result)
    payload = {
        "ok": all(check.available for check in checks),
        "install_requested": args.install,
        "checks": [asdict(check) for check in checks],
        "install_results": [asdict(check) for check in install_results],
        "project_init": asdict(init_result) if init_result else None,
        "dependencies": [
            {"name": label, "command": command, "package": package}
            for label, command, package in DEPENDENCIES
        ],
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for check in checks:
            print(f"{'OK' if check.available else 'MISSING'} {check.name}: {check.detail}")
        for result in install_results:
            print(f"{'INSTALLED' if result.available else 'FAILED'} {result.name}: {result.detail}")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
