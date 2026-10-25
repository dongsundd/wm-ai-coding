"""Host-neutral skill roles. Profiles constrain work without becoming workflow states."""
from __future__ import annotations

from pathlib import Path
import yaml


def load_registry(root: Path) -> dict:
    data = yaml.safe_load((root / "skills/registry.yaml").read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != 1 or not isinstance(data.get("skills"), dict):
        raise ValueError("invalid skill registry")
    return data["skills"]


def validate_registry(root: Path) -> list[str]:
    registry = load_registry(root)
    found = {p.parent.name for p in (root / "skills").glob("*/SKILL.md")}
    findings = [f"unregistered skill: {name}" for name in sorted(found - registry.keys())]
    for name, role in registry.items():
        if name not in found:
            findings.append(f"missing skill: {name}")
        if (not isinstance(role, dict) or role.get("role") not in {"controller", "stage", "support", "profile", "operation"}
                or not isinstance(role.get("stages"), list)):
            findings.append(f"invalid skill role: {name}")
    return findings


def role_for(workflow, skill: str, stage: str) -> str | None:
    # Installed wheels may carry a data-only registry next to workflow.yaml.
    root = workflow.path.parent.parent.parent
    path = root / "skills/registry.yaml"
    data = load_registry(root) if path.is_file() else yaml.safe_load(
        (workflow.path.parent / "registry.yaml").read_text(encoding="utf-8"))["skills"]
    entry = data.get(skill, {})
    return entry.get("role") if stage in entry.get("stages", []) else None
