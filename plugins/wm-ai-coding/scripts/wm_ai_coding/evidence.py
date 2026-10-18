from __future__ import annotations

import hashlib
import re
from pathlib import Path


TASK_HEADING = re.compile(r"(?m)^###\s+Task\s+\d+\s*:[^\n]+$")
REQUIRED_FIELDS = ("Requirement", "Outcome", "Files", "Interfaces", "Acceptance", "Verification")


def digest(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def task_definition_digest(path: Path) -> str | None:
    if not path.is_file():
        return None
    body = path.read_text(encoding="utf-8")
    normalized = re.sub(r"(?mi)^(\s*-\s*)\[[ xX]\]", r"\1[ ]", body)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def task_contract(body: str) -> list[str]:
    matches = list(TASK_HEADING.finditer(body))
    if not matches:
        return ["tasks.md has no task sections"]
    findings: list[str] = []
    for index, match in enumerate(matches):
        section = body[match.end() : matches[index + 1].start() if index + 1 < len(matches) else len(body)]
        for field in REQUIRED_FIELDS:
            if not re.search(rf"(?mi)^\s*-\s*\[[ xX]\]\s*{field}\b", section):
                findings.append(f"{match.group(0)} is missing {field.lower()}")
    return findings


def inspect_change(change: Path) -> dict:
    design = change / "design.md"
    tasks = change / "tasks.md"
    verification = change / "verification.md"
    design_body = design.read_text(encoding="utf-8") if design.is_file() else ""
    tasks_body = tasks.read_text(encoding="utf-8") if tasks.is_file() else ""
    verification_body = verification.read_text(encoding="utf-8") if verification.is_file() else ""
    sections = list(TASK_HEADING.finditer(tasks_body))
    open_tasks = 0
    completed_tasks = 0
    for index, match in enumerate(sections):
        section = tasks_body[match.end() : sections[index + 1].start() if index + 1 < len(sections) else len(tasks_body)]
        states = re.findall(r"(?mi)^\s*-\s*\[([ xX])\]", section)
        if states and all(value.lower() == "x" for value in states):
            completed_tasks += 1
        else:
            open_tasks += 1
    specs = list((change / "specs").glob("**/*.md")) if (change / "specs").is_dir() else []
    return {
        "proposal": (change / "proposal.md").is_file(),
        "specs": bool(specs),
        "design": design.is_file(),
        "design_digest": digest(design),
        "codegraph_impact": bool(re.search(r"(?mi)^##\s+CodeGraph impact analysis\s*$", design_body)),
        "tasks": tasks.is_file(),
        "tasks_digest": task_definition_digest(tasks),
        "task_contract_valid": tasks.is_file() and not task_contract(tasks_body),
        "task_findings": task_contract(tasks_body) if tasks.is_file() else ["tasks.md is missing"],
        "open_tasks": open_tasks,
        "completed_tasks": completed_tasks,
        "verification": verification.is_file(),
        "codegraph_recheck": bool(re.search(r"(?mi)^##\s+CodeGraph (?:impact )?recheck\s*$", verification_body)),
    }
