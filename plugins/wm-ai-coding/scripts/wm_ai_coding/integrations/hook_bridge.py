"""Resolve hook context and return host protocol data without owning CLI streams."""
from __future__ import annotations

from pathlib import Path

from ..infrastructure.paths import workflow_path
from wm_ai_coding.infrastructure.workflow import load_workflow
from wm_ai_coding.lifecycle.machine import StateMachine
from wm_ai_coding.integrations.hooks import CAPABILITIES, handle_hook, decision
from .bootstrap import startup, context_output


def dispatch(host: str, event: str, payload: dict, *, repo: Path | None = None) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("hook payload must be a JSON object")
    if host not in CAPABILITIES or event not in CAPABILITIES[host]['events']:
        raise ValueError('unsupported host/event')
    if event == 'SubagentStart':
        payload = dict(payload, parent_session_id=payload.get('session_id') or 'native-parent')
    if repo is None:
        cwd = Path(payload.get("cwd", Path.cwd())).resolve()
        for candidate in (cwd, *cwd.parents):
            if (candidate / '.wm/state.json').is_file():
                repo = candidate
                break
            if (candidate / '.git').exists():
                break  # An independent checkout must never inherit its parent's WM state.
    if repo is None:
        if event in {'SessionStart', 'SubagentStart', 'session-start', 'context'}:
            return context_output(host, event, startup(host, payload))
        if event == 'UserPromptSubmit':
            return context_output(host, event, 'WM: no active change; development requests enter development-workflow; read-only requests need no initialization.')
        return {}
    machine = StateMachine(Path(repo).resolve(), load_workflow(workflow_path()))
    return handle_hook(machine, host, event, payload)


def failure(host: str, event: str, error: Exception) -> dict:
    message = f"WM hook error: {error}"
    return decision(host, False, message) if event in {"PreToolUse", "pre-tool-use"} else {"systemMessage": message}
