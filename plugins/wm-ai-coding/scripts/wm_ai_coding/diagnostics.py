"""Bounded recovery context and read-only environment diagnostics."""
from __future__ import annotations

import json
import shutil
import sys

from .hooks import CAPABILITIES
from .identity import VERSION, verify_bundle
from .registry import validate_registry


def brief(machine, change=None, *, limit=2048) -> dict:
    state = machine.status(); name = change or state.get("active_change")
    if not name or name not in state["changes"]:
        return {"controller": "development-workflow", "next": "select or create a change"}
    item = state["changes"][name]
    result = {"controller": "development-workflow", "change": name[:120], "stage": item["stage"], "status": item["status"],
              "task": (item.get("current_task") or {}).get("id"), "missing_gates": item.get("missing_gates", [])[:12],
              "handoff": (item.get("last_handoff") or {}).get("id"),
              "next": "wm recovery --change " + name[:120], "integrity": (item.get("integrity") or {}).get("status")}
    if len(json.dumps(result).encode()) > limit:
        return {"controller": "development-workflow", "next": "wm recovery (brief exceeds budget)"}
    return result


def doctor(machine) -> dict:
    root = __import__('pathlib').Path(__file__).resolve().parents[2]
    findings = []
    try:
        validation = machine.validate(); findings.extend(validation["findings"])
    except (OSError, ValueError, RuntimeError) as exc:
        findings.append(str(exc))
    if (root / "skills/registry.yaml").is_file():
        findings.extend(validate_registry(root))
    release = verify_bundle(root)
    if not release["valid"]:
        findings.append("release bundle missing or changed; rebuild before distribution")
    tools = {name: shutil.which(name) or shutil.which(name + ".cmd") for name in ("codegraph", "playwright-mcp")}
    return {"valid": not findings, "version": VERSION, "python": sys.version, "release": release,
            "tools": tools, "capabilities": CAPABILITIES, "findings": findings,
            "limitations": ["PATH detection is not an MCP handshake", "missing historical archives are not reconstructed"]}
