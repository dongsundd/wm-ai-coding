"""Shared runtime asset location for source checkouts and installed wheels."""
from pathlib import Path
import os
import sys
from wm_ai_coding.infrastructure.workflow import WorkflowError


def plugin_root() -> Path:
    if configured := os.environ.get("WM_PLUGIN_ROOT"):
        return Path(configured).resolve()
    return Path(__file__).resolve().parents[3]


def workflow_path() -> Path:
    candidates = []
    if configured := os.environ.get("WM_WORKFLOW_PATH"):
        candidates.append(Path(configured))
    candidates.extend(
        (
            plugin_root() / "skills" / "development-workflow" / "config" / "workflow.yaml",
            Path(sys.prefix) / "share" / "wm-ai-coding" / "workflow.yaml",
        )
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise WorkflowError("development-workflow workflow.yaml was not found")


