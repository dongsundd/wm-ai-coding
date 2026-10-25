"""Local execution evidence. These records are not security attestations."""
from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .evidence import digest, inspect_change, requirement_inventory
from .identity import VERSION, PROTOCOL_VERSION, fingerprint


EXCLUDED = {".git", ".wm", "sdd", ".codegraph", ".playwright-mcp", ".worktrees",
            "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".venv", "venv",
            "node_modules", "build", "dist", ".idea"}


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def workspace_files(repo: Path, *, process: bool = False) -> dict[str, str]:
    """Stable file inventory; no mtime-only cache and no following directory symlinks."""
    files = {}
    excluded = EXCLUDED - {"sdd"} if process else EXCLUDED
    for directory, dirs, names in os.walk(repo, followlinks=False):
        dirs[:] = sorted(name for name in dirs if name not in excluded and not name.endswith(".egg-info"))
        for name in sorted(names):
            path = Path(directory) / name
            files[path.relative_to(repo).as_posix()] = (fingerprint(os.readlink(path)) if path.is_symlink() else digest(path))
    return files


def workspace_digest(repo: Path) -> str:
    return fingerprint(workspace_files(repo))


def environment_identity(repo: Path, checks: list[dict]) -> dict:
    names = sorted({name for check in checks for name in check.get("environment", [])})
    artifacts = sorted({name for check in checks for name in check.get("artifacts", [])})
    for name in artifacts:
        if not scoped(repo, name).is_file():
            raise ValueError(f"declared artifact missing: {name}")
    executables = sorted({check["argv"][0] for check in checks})
    resolved = {}
    for executable in executables:
        candidate = shutil.which(executable) or str(repo / executable)
        path = Path(candidate)
        resolved[executable] = {"path": str(path.resolve()), "sha256": digest(path)}
    runtime_files = {p.name: digest(p) for p in Path(__file__).resolve().parent.glob("*.py")}
    return {"runtime": VERSION, "runtime_digest": fingerprint(runtime_files), "protocol": PROTOCOL_VERSION, "python": sys.version,
            "executables": resolved,
            "environment": {name: fingerprint(os.environ.get(name)) for name in names},
            "artifacts": {name: digest(scoped(repo, name)) for name in artifacts}}


def scoped(repo: Path, value: str) -> Path:
    path = (repo / value).resolve()
    if not path.is_relative_to(repo.resolve()):
        raise ValueError("artifact escapes repository")
    return path


def inputs(repo: Path, change: Path) -> dict:
    evidence = inspect_change(change)
    checks = load_plan(change)
    return {"planning": evidence["planning_digest"], "tasks": evidence["tasks_digest"],
            "plan": digest(change / "verification-plan.json"), "workspace": workspace_digest(repo),
            "environment": fingerprint(environment_identity(repo, checks))}


def load_plan(change: Path) -> list[dict]:
    try:
        data = json.loads((change / "verification-plan.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("verification-plan.json is missing or invalid") from exc
    checks = data.get("checks") if isinstance(data, dict) else None
    if not isinstance(checks, list) or not checks:
        raise ValueError("verification plan needs non-empty checks")
    seen: set[str] = set()
    for check in checks:
        if not isinstance(check, dict) or not isinstance(check.get("id"), str) or not check["id"].strip():
            raise ValueError("check needs a non-empty id")
        if check["id"] in seen:
            raise ValueError("duplicate check id")
        seen.add(check["id"])
        argv = check.get("argv")
        if not isinstance(argv, list) or not argv or not all(isinstance(arg, str) and arg for arg in argv):
            raise ValueError("check argv must be a non-empty string list")
        if check.get("kind", "test") not in {"test", "build", "static", "browser", "review"}:
            raise ValueError("invalid check kind")
        if "task" in check and not isinstance(check["task"], str):
            raise ValueError("invalid check task")
        for field in ("requirements", "scenarios", "environment", "artifacts"):
            refs = check.get(field, [])
            if not isinstance(refs, list) or not all(isinstance(ref, str) and ref.strip() for ref in refs):
                raise ValueError(f"check {field} must be a string list")
    return checks


def run_check(repo: Path, change: Path, check_id: str, *, timeout: float = 300, context: dict | None = None) -> dict:
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be finite and positive")
    checks = load_plan(change)
    check = next((item for item in checks if item["id"] == check_id), None)
    if check is None:
        raise ValueError(f"unknown check: {check_id}")
    run_id = uuid4().hex
    directory = repo / ".wm" / "runs" / run_id
    directory.mkdir(parents=True)
    record = {"id": run_id, "change": change.name, "check_id": check_id, "argv": check["argv"],
              "started_at": timestamp(), "inputs": inputs(repo, change), "status": "running",
              "exit_code": None, "task": check.get("task"), "kind": check.get("kind", "test"),
              "check_digest": fingerprint(check), "trace_id": run_id, "workspace_id": str(repo.resolve())}
    record.update(context or {})
    path = directory / "record.json"
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    started = time.monotonic()
    try:
        with (directory / "stdout.log").open("wb") as stdout, (directory / "stderr.log").open("wb") as stderr:
            process = subprocess.run(check["argv"], cwd=repo, stdin=subprocess.DEVNULL,
                                     stdout=stdout, stderr=stderr, timeout=timeout, check=False)
        record.update(status="passed" if process.returncode == 0 else "failed", exit_code=process.returncode)
    except subprocess.TimeoutExpired:
        record["status"] = "timed_out"
    except OSError as exc:
        record.update(status="failed", error=str(exc))
    except KeyboardInterrupt:
        record["status"] = "cancelled"
        raise
    finally:
        record["finished_at"] = timestamp()
        record["duration_ms"] = round((time.monotonic() - started) * 1000)
        record["stdout_bytes"] = (directory / "stdout.log").stat().st_size if (directory / "stdout.log").exists() else 0
        record["stderr_bytes"] = (directory / "stderr.log").stat().st_size if (directory / "stderr.log").exists() else 0
        record["outputs"] = inputs(repo, change)
        record["stdout_sha256"] = digest(directory / "stdout.log")
        record["stderr_sha256"] = digest(directory / "stderr.log")
        temp = directory / "record.tmp"
        temp.write_text(json.dumps(record, indent=2), encoding="utf-8")
        os.replace(temp, path)
    return record


def verification_findings(repo: Path, change: Path, *, change_name: str | None = None) -> list[str]:
    try:
        checks = load_plan(change)
        requirements, scenarios = requirement_inventory(change)
        current = inputs(repo, change)
    except (OSError, ValueError) as exc:
        return [str(exc)]
    findings: list[str] = []
    if not requirements or not scenarios:
        findings.append("delta specs need requirement and scenario headings")
    covered_requirements = {ref for check in checks for ref in check.get("requirements", [])}
    covered_scenarios = {ref for check in checks for ref in check.get("scenarios", [])}
    for label, expected, covered in (("requirement", requirements, covered_requirements),
                                     ("scenario", scenarios, covered_scenarios)):
        findings.extend(f"uncovered {label}: {ref}" for ref in sorted(expected - covered))
        findings.extend(f"unknown {label}: {ref}" for ref in sorted(covered - expected))
    records = []
    for path in (repo / ".wm" / "runs").glob("*/record.json"):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(record, dict) and record.get("change") == (change_name or change.name):
                records.append((record, path.parent))
        except (OSError, ValueError):
            findings.append(f"invalid run record: {path.parent.name}")
    for check in checks:
        matching = [(record, path) for record, path in records if record.get("check_id") == check["id"]]
        if not matching:
            findings.append(f"check has no run: {check['id']}")
            continue
        record, directory = max(matching, key=lambda item: str(item[0].get("started_at", "")))
        if (record.get("status") != "passed" or record.get("exit_code") != 0
                or record.get("inputs") != current or record.get("outputs") != current
                or record.get("argv") != check["argv"]
                or not record.get("stdout_sha256") or not record.get("stderr_sha256")
                or record.get("stdout_sha256") != digest(directory / "stdout.log")
                or record.get("stderr_sha256") != digest(directory / "stderr.log")):
            findings.append(f"check has failed, incomplete or stale run: {check['id']}")
    return findings


def latest_run(repo: Path, change_name: str, check_id: str):
    records = []
    for path in (repo / ".wm/runs").glob("*/record.json"):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            if record.get("change") == change_name and record.get("check_id") == check_id:
                records.append((record, path.parent))
        except (OSError, ValueError, AttributeError):
            continue
    return max(records, key=lambda item: item[0].get("started_at", "")) if records else None


def task_acceptance(repo: Path, change: Path, task: dict, *, handoff_id: str) -> list[dict]:
    checks = load_plan(change)
    current = inputs(repo, change)
    declared = task.get("checks", [])
    if not declared:
        raise ValueError("task acceptance requires - Check: identifiers")
    accepted = []
    for check_id in declared:
        check = next((c for c in checks if c["id"] == check_id and c.get("task") == task["id"]), None)
        latest = latest_run(repo, change.name, check_id)
        if check is None or latest is None:
            raise ValueError("task acceptance has no matching check/run")
        record, directory = latest
        if (record.get("status") != "passed" or record.get("exit_code") != 0
                or record.get("inputs") != current or record.get("outputs") != current
                or record.get("check_digest") != fingerprint(check)
                or record.get("task") != task["id"] or record.get("handoff_id") != handoff_id
                or record.get("stdout_sha256") != digest(directory / "stdout.log")
                or record.get("stderr_sha256") != digest(directory / "stderr.log")):
            raise ValueError("task acceptance run is failed, stale or belongs to another handoff")
        accepted.append(record)
    return accepted
