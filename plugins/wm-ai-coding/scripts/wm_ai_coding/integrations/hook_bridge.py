"""Resolve hook context and return host protocol data without owning CLI streams."""
from __future__ import annotations

from pathlib import Path

from ..infrastructure.paths import workflow_path
from wm_ai_coding.infrastructure.workflow import load_workflow
from wm_ai_coding.lifecycle.machine import StateMachine
from wm_ai_coding.integrations.hooks import handle_hook, decision


def dispatch(host: str, event: str, payload: dict, *, repo: Path | None = None) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("hook payload must be a JSON object")
    if repo is None:
        cwd = Path(payload.get("cwd", Path.cwd())).resolve()
        repo = next((p for p in (cwd, *cwd.parents) if (p / ".wm/state.json").is_file()), None)
    if repo is None:
        return {"hookSpecificOutput": {"hookEventName": event, "additionalContext":
            "WM: development work enters development-workflow; initialize explicitly with wm init --no-gitignore."}} if event in {"SessionStart", "UserPromptSubmit"} else {}
    machine = StateMachine(Path(repo).resolve(), load_workflow(workflow_path()))
    return handle_hook(machine, host, event, payload)


def failure(host: str, event: str, error: Exception) -> dict:
    message = f"WM hook error: {error}"
    return decision(host, False, message) if event in {"PreToolUse", "pre-tool-use"} else {"systemMessage": message}
