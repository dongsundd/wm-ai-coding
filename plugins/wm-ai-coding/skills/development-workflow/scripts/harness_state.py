#!/usr/bin/env python3
"""Compatibility wrapper for the unified WM CLI."""

from __future__ import annotations

import sys
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))

from wm_ai_coding.entrypoint import main
from wm_ai_coding.evidence.inspection import inspect_change


def inspect(change: Path) -> dict[str, object]:
    """Legacy read-only evidence shape used by existing integrations."""
    evidence = inspect_change(change)
    if not evidence["proposal"]:
        next_stage = "clarify"
    elif not evidence["specs"] or not evidence["design"]:
        next_stage = "specify"
    elif not evidence["tasks"] or not evidence["task_contract_valid"]:
        next_stage = "tasks"
    elif evidence["open_tasks"]:
        next_stage = "apply"
    elif not evidence["verification"]:
        next_stage = "verify"
    else:
        next_stage = "close"
    missing = []
    for key in ("proposal", "specs", "design"):
        if not evidence[key]:
            missing.append(key)
    if evidence["design"] and not evidence["task_contract_valid"]:
        missing.append("task_contract")
    return {
        "change": change.name,
        "path": str(change),
        "artifacts": evidence,
        "missing_gates": missing,
        "next_stage": next_stage,
        "tasks": {
            "completed": evidence["completed_tasks"],
            "open": evidence["open_tasks"],
            "all_complete": evidence["tasks"] and evidence["task_contract_valid"] and evidence["open_tasks"] == 0,
            "contract_valid": evidence["task_contract_valid"],
            "contract_findings": evidence["task_findings"],
        },
    }


if __name__ == "__main__":
    arguments = sys.argv[1:]
    if arguments and arguments[0] == "status":
        # Legacy form: harness_state.py status <repo> [change]
        repo = arguments[1] if len(arguments) > 1 else "."
        change = arguments[2] if len(arguments) > 2 else None
        arguments = ["--repo", repo, "status", *(["--change", change] if change else [])]
    raise SystemExit(main(arguments))
