"""Portable evidence and archive integrity, independent of local .wm state."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from .evidence import digest
from .identity import fingerprint
from .runs import latest_run, load_plan


def inventory(root: Path) -> dict:
    files = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("archive cannot contain symlinks")
        if path.is_file() and path != root / "archive-manifest.json":
            files[path.relative_to(root).as_posix()] = digest(path)
    return files


def write_manifest(root: Path) -> str:
    files = inventory(root)
    manifest = {"schema_version": 1, "files": files, "digest": fingerprint(files)}
    path = root / "archive-manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return digest(path)


def verify_archive(root: Path, expected: str | None = None) -> dict:
    if not root.is_dir():
        return {"valid": False, "status": "missing", "findings": [f"missing archive: {root}"]}
    try:
        path = root / "archive-manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        files = inventory(root)
        valid = (manifest.get("schema_version") == 1 and manifest.get("files") == files
                 and manifest.get("digest") == fingerprint(files) and (expected is None or expected == digest(path)))
        return {"valid": valid, "status": "valid" if valid else "changed",
                "findings": [] if valid else ["archive files or manifest changed"],
                "trust": "local content integrity; not an authenticated attestation"}
    except (OSError, ValueError, TypeError):
        return {"valid": False, "status": "unknown", "findings": ["archive manifest missing or invalid"]}


def export_evidence(repo: Path, change: Path, receipts: dict | None = None) -> None:
    destination = change / "evidence/runs"
    selected = {}
    for check in load_plan(change):
        latest = latest_run(repo, change.name, check["id"])
        if latest is None:
            raise ValueError(f"missing run for {check['id']}")
        record, directory = latest
        selected[record["id"]] = (record, directory)
    for receipt in (receipts or {}).values():
        for record in receipt.get("runs", []):
            run_id = record["id"]
            if not __import__('re').fullmatch(r"[a-f0-9]{32}", run_id):
                raise ValueError("invalid receipt run ID")
            selected[run_id] = (record, repo / ".wm/runs" / run_id)
    for record, directory in selected.values():
        target = destination / record["id"]
        target.mkdir(parents=True, exist_ok=True)
        for name in ("record.json", "stdout.log", "stderr.log"):
            shutil.copyfile(directory / name, target / name)
    (change / "evidence/task-receipts.json").write_text(json.dumps(receipts or {}, indent=2), encoding="utf-8")


def integrity_for(repo: Path, item: dict) -> dict:
    relative = item.get("archive_path") or (item.get("archive_intent") or {}).get("target")
    if not relative:
        return {"valid": False, "status": "unknown", "findings": ["archive path missing"]}
    path = (repo / relative).resolve()
    if not path.is_relative_to(repo.resolve()):
        return {"valid": False, "status": "invalid", "findings": ["archive path escapes repository"]}
    return verify_archive(path, item.get("archive_manifest_sha256"))
