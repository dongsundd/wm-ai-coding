"""Content-addressed release identity; local hashes are not attestations."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

VERSION = "0.9.1"
PROTOCOL_VERSION = 2


def fingerprint(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def bundle_files(root: Path) -> dict[str, str]:
    excluded = {"build", "dist", ".git", "__pycache__", ".pytest_cache"}
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file() and not p.is_symlink()
            and not any(x in excluded or x.endswith(".egg-info") for x in p.relative_to(root).parts)
            and p.name != "bundle-manifest.json"}


def seal_bundle(root: Path) -> dict:
    files = bundle_files(root)
    manifest = {"version": VERSION, "protocol": PROTOCOL_VERSION, "files": files, "digest": fingerprint(files)}
    (root / "bundle-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8", newline="\n")
    return manifest


def verify_bundle(root: Path) -> dict:
    try:
        manifest = json.loads((root / "bundle-manifest.json").read_text(encoding="utf-8"))
        files = bundle_files(root)
        valid = manifest.get("files") == files and manifest.get("digest") == fingerprint(files) and manifest.get("version") == VERSION
        return {"valid": valid, "version": VERSION, "path": str(root), "digest": fingerprint(files)}
    except (OSError, ValueError):
        return {"valid": False, "version": VERSION, "path": str(root), "finding": "bundle manifest missing or invalid"}
