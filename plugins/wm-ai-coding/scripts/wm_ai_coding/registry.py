"""Host-neutral skill roles. Profiles constrain work without becoming workflow states."""
from __future__ import annotations

from pathlib import Path
import re
import yaml


def load_registry(root: Path) -> dict:
    data = yaml.safe_load((root / "skills/registry.yaml").read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != 1 or not isinstance(data.get("skills"), dict):
        raise ValueError("invalid skill registry")
    return data["skills"]


def validate_registry(root: Path) -> list[str]:
    registry = load_registry(root)
    data = yaml.safe_load((root / "skills/registry.yaml").read_text(encoding="utf-8"))
    found = {p.parent.name for p in (root / "skills").glob("*/SKILL.md")}
    findings = [f"unregistered skill: {name}" for name in sorted(found - registry.keys())]
    for name, role in registry.items():
        if not valid_name(name):
            findings.append(f"invalid skill name: {name}")
        if name not in found:
            findings.append(f"missing skill: {name}")
        else:
            try:
                text = (root / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
                metadata = yaml.safe_load(text.split("---", 2)[1])
                if not isinstance(metadata, dict) or metadata.get("name") != name:
                    findings.append(f"skill name differs from directory: {name}")
            except (ValueError, IndexError, yaml.YAMLError):
                findings.append(f"invalid skill frontmatter: {name}")
        if (not isinstance(role, dict) or role.get("role") not in {"controller", "stage", "support", "profile", "operation"}
                or not isinstance(role.get("stages"), list)):
            findings.append(f"invalid skill role: {name}")
    findings.extend(alias_findings(registry, data.get("aliases", {}), data.get("stage_aliases", {})))
    return findings


def valid_name(value: str) -> bool:
    return isinstance(value, str) and 0 < len(value) < 64 and bool(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value))


def alias_findings(skills: dict, aliases, stage_aliases=None) -> list[str]:
    if not isinstance(aliases, dict):
        return ["skill aliases must be a mapping"]
    findings = [f"invalid skill alias: {old} -> {target}" for old, target in aliases.items()
                if not valid_name(old) or not valid_name(target) or old in skills or target not in skills]
    if stage_aliases is not None:
        if not isinstance(stage_aliases, dict):
            return findings + ["stage aliases must be a mapping"]
        for old, overrides in stage_aliases.items():
            if old not in aliases or not isinstance(overrides, dict):
                findings.append(f"invalid stage alias: {old}")
                continue
            for stage, target in overrides.items():
                if (not valid_name(target) or target not in skills
                        or stage not in skills.get(target, {}).get("stages", [])):
                    findings.append(f"invalid stage alias: {old} / {stage} -> {target}")
    return findings


def workflow_registry(workflow) -> dict:
    # Installed wheels may carry a data-only registry next to workflow.yaml.
    root = workflow.path.parent.parent.parent
    path = root / "skills/registry.yaml"
    if not path.is_file():
        path = workflow.path.parent / "registry.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def canonical_skill(workflow, skill: str, stage: str | None = None) -> str:
    data = workflow_registry(workflow)
    return data.get("stage_aliases", {}).get(skill, {}).get(stage, data.get("aliases", {}).get(skill, skill))


def role_for(workflow, skill: str, stage: str) -> str | None:
    data = workflow_registry(workflow)
    selected = data.get("stage_aliases", {}).get(skill, {}).get(stage, data.get("aliases", {}).get(skill, skill))
    entry = data["skills"].get(selected, {})
    return entry.get("role") if stage in entry.get("stages", []) else None
