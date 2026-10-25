from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


TASK_HEADING = re.compile(r"(?m)^###\s+Task\s+\d+\s*:[^\n]+$")
REQUIRED_FIELDS = ("Requirement", "Outcome", "Files", "Interfaces", "Acceptance", "Verification")
VERIFICATION_READY = re.compile(r"(?i)\bready for archiv(?:e|ing)\b")
VERIFICATION_INCOMPLETE = re.compile(
    r"(?i)\bnot verified\b|\bskipped checks?\b|\bnot ready for archiv(?:e|ing)\b"
    r"|\b[1-9]\d*\s+(?:critical|blocking)\s+(?:issues?|findings?)\b")


def digest(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def has_content(path: Path) -> bool:
    return path.is_file() and bool(path.read_text(encoding="utf-8").strip())


def verification_report_valid(path: Path) -> bool:
    if not has_content(path):
        return False
    body = path.read_text(encoding="utf-8")
    return bool(VERIFICATION_READY.search(body)) and not VERIFICATION_INCOMPLETE.search(body)


def markdown_section_has_content(body: str, heading: str) -> bool:
    match = re.search(rf"(?mi)^##\s+{re.escape(heading)}\s*$", body)
    if not match:
        return False
    remainder = body[match.end() :]
    next_heading = re.search(r"(?m)^##\s+", remainder)
    section = remainder[: next_heading.start()] if next_heading else remainder
    return bool(section.strip())


def tree_digest(root: Path) -> str | None:
    files = sorted(path for path in root.glob("**/*.md") if path.is_file()) if root.is_dir() else []
    if not root.is_dir():
        return None
    value = hashlib.sha256()
    for path in files:
        value.update(path.relative_to(root).as_posix().encode("utf-8"))
        value.update(b"\0")
        value.update(path.read_bytes())
        value.update(b"\0")
    return value.hexdigest()


def artifact_tree_digest(root: Path) -> str | None:
    """Include JSON, attachments and other artifacts in archive recovery identity."""
    if not root.is_dir():
        return None
    value = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("archive artifacts must not contain symlinks")
        if path.is_file():
            value.update(path.relative_to(root).as_posix().encode())
            value.update(b"\0")
            value.update(path.read_bytes())
            value.update(b"\0")
    return value.hexdigest()


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
    numbers = re.findall(r"(?m)^###\s+Task\s+(\d+)\s*:", body)
    if len(set(numbers)) != len(numbers):
        findings.append("task identifiers must be unique")
    for index, match in enumerate(matches):
        section = body[match.end() : matches[index + 1].start() if index + 1 < len(matches) else len(body)]
        for field in REQUIRED_FIELDS:
            if not re.search(rf"(?mi)^[ \t]*-[ \t]*\[[ xX]\][ \t]*{field}:[ \t]*\S[^\n]*", section):
                findings.append(f"{match.group(0)} is missing {field.lower()}")
    states = parse_tasks(body)
    graph = {task["id"]: set(task["depends_on"]) for task in states}
    for task in states:
        for dependency in task["depends_on"]:
            if dependency not in graph:
                findings.append(f"{task['id']} has unknown dependency: {dependency}")
            elif task["complete"] and not next(item["complete"] for item in states if item["id"] == dependency):
                findings.append(f"{task['id']} completed before dependency: {dependency}")
    pending = dict(graph)
    while pending:
        ready = {name for name, dependencies in pending.items() if not dependencies}
        if not ready:
            findings.append("task dependencies contain a cycle or missing target")
            break
        pending = {name: dependencies - ready for name, dependencies in pending.items() if name not in ready}
    return findings


def parse_tasks(body: str) -> list[dict]:
    sections = list(TASK_HEADING.finditer(body))
    tasks = []
    for index, match in enumerate(sections):
        section = body[match.end(): sections[index + 1].start() if index + 1 < len(sections) else len(body)]
        markers = re.findall(r"(?mi)^\s*-\s*\[([ xX])\]", section)
        number = re.search(r"Task\s+(\d+)", match.group())[1]
        dependency_line = re.search(r"(?mi)^- Depends on:\s*([^\n]*)", section)
        dependencies = [] if dependency_line is None or dependency_line[1].strip().lower() == "none" else [
            value.strip() for value in dependency_line[1].split(",") if value.strip()]
        tasks.append({"index": index + 1, "id": f"task-{number}",
                      "title": match.group().removeprefix("###").strip(),
                      "complete": bool(markers) and all(value.lower() == "x" for value in markers),
                      "depends_on": dependencies,
                      "checks": re.findall(r"(?mi)^- Check:[ \t]*(\S+)[ \t]*$", section)})
    return tasks


def ready_tasks(tasks: list[dict]) -> list[dict]:
    complete = {task["id"] for task in tasks if task["complete"]}
    return [task for task in tasks if not task["complete"] and set(task["depends_on"]) <= complete]


def inspect_change(change: Path) -> dict:
    design = change / "design.md"
    tasks = change / "tasks.md"
    verification = change / "verification.md"
    design_body = design.read_text(encoding="utf-8") if design.is_file() else ""
    tasks_body = tasks.read_text(encoding="utf-8") if tasks.is_file() else ""
    task_states = parse_tasks(tasks_body)
    completed_tasks = sum(1 for task in task_states if task["complete"])
    open_tasks = len(task_states) - completed_tasks
    specs = list((change / "specs").glob("**/*.md")) if (change / "specs").is_dir() else []
    findings = task_contract(tasks_body) if tasks.is_file() else ["tasks.md is missing"]
    planning = {"proposal": digest(change / "proposal.md"), "specs": tree_digest(change / "specs"),
                "design": digest(design)}
    if (change / "test-design.md").is_file():
        planning["test_design"] = digest(change / "test-design.md")
    return {
        "proposal": has_content(change / "proposal.md"),
        "specs": any(has_content(path) for path in specs),
        "design": has_content(design),
        "design_digest": digest(design),
        "planning_digest": hashlib.sha256(json.dumps(planning, sort_keys=True).encode()).hexdigest(),
        "frontend_design": markdown_section_has_content(design_body, "Frontend design"),
        "structural_analysis": markdown_section_has_content(design_body, "Structural analysis"),
        "tasks": tasks.is_file(),
        "tasks_digest": task_definition_digest(tasks),
        "task_contract_valid": tasks.is_file() and not findings,
        "task_findings": findings,
        "task_states": task_states,
        "open_tasks": open_tasks,
        "completed_tasks": completed_tasks,
        "verification": verification_report_valid(verification),
    }


def requirement_inventory(change: Path) -> tuple[set[str], set[str]]:
    """Stable keys are capability::requirement[::scenario], using authored headings."""
    requirements: set[str] = set()
    scenarios: set[str] = set()
    for path in sorted((change / "specs").glob("**/spec.md")):
        capability = path.parent.relative_to(change / "specs").as_posix()
        requirement = None
        for line in path.read_text(encoding="utf-8").splitlines():
            if match := re.match(r"^### Requirement:\s*(\S.*)", line):
                requirement = f"{capability}::{match[1].strip()}"
                if requirement in requirements:
                    raise ValueError(f"duplicate requirement: {requirement}")
                requirements.add(requirement)
            elif match := re.match(r"^#### Scenario:\s*(\S.*)", line):
                if requirement is None:
                    raise ValueError(f"scenario has no requirement: {path.name}")
                key = f"{requirement}::{match[1].strip()}"
                if key in scenarios:
                    raise ValueError(f"duplicate scenario: {key}")
                scenarios.add(key)
    return requirements, scenarios
