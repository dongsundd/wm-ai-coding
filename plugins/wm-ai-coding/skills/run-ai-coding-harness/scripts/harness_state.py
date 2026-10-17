#!/usr/bin/env python3
"""Report objective OpenSpec harness evidence without mutating the repository."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def change_dirs(repo: Path) -> list[Path]:
    root = repo / "sdd" / "changes"
    if not root.is_dir():
        return []
    return sorted(p for p in root.iterdir() if p.is_dir() and p.name != "archive")


def inspect(change: Path) -> dict[str, object]:
    tasks = change / "tasks.md"
    design = change / "design.md"
    body = tasks.read_text(encoding="utf-8") if tasks.is_file() else ""
    design_body = design.read_text(encoding="utf-8") if design.is_file() else ""
    verification = change / "verification.md"
    verification_body = verification.read_text(encoding="utf-8") if verification.is_file() else ""
    completed = len(re.findall(r"(?mi)^\s*-\s*\[[xX]\]", body))
    open_tasks = len(re.findall(r"(?mi)^\s*-\s*\[ \]", body))
    specs_root = change / "specs"
    specs = sorted(str(p.relative_to(change)) for p in specs_root.glob("**/*.md")) if specs_root.is_dir() else []
    return {
        "change": change.name,
        "path": str(change),
        "artifacts": {
            "proposal": (change / "proposal.md").is_file(),
            "specs": specs,
            "design": design.is_file(),
            "codegraph_impact": bool(re.search(r"(?mi)^##\s+CodeGraph impact analysis\s*$", design_body)),
            "technology_profiles": bool(re.search(r"(?mi)^##\s+Technology profiles\s*$", design_body)),
            "playwright_research": bool(re.search(r"(?mi)^##\s+Playwright research\s*$", design_body)),
            "tasks": tasks.is_file(),
            "verification": verification.is_file(),
            "playwright_verification": bool(re.search(r"(?mi)^##\s+Playwright end-to-end verification\s*$", verification_body)),
            "technology_profile_verification": bool(re.search(r"(?mi)^##\s+Technology profile verification\s*$", verification_body)),
        },
        "tasks": {
            "completed": completed,
            "open": open_tasks,
            "all_complete": tasks.is_file() and open_tasks == 0,
            "profile_entries": len(re.findall(r"(?mi)^\s*(?:[-*]\s*)?(?:\*\*)?Profile(?:\*\*)?\s*:", body)),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect OpenSpec harness state")
    parser.add_argument("command", choices=["status"])
    parser.add_argument("repo", type=Path)
    parser.add_argument("change", nargs="?")
    args = parser.parse_args()
    repo = args.repo.resolve()
    changes = change_dirs(repo)
    if args.change:
        changes = [p for p in changes if p.name == args.change]
    print(json.dumps({"repo": str(repo), "changes": [inspect(p) for p in changes]}, ensure_ascii=False, indent=2))
    return 0 if changes else 1


if __name__ == "__main__":
    raise SystemExit(main())
