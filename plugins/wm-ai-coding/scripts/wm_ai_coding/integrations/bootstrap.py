"""Shared static startup contract; live state is deliberately never cached here."""
from functools import lru_cache
from pathlib import Path
import sys

from ..infrastructure.paths import plugin_root

MAPPINGS = {
    'claude': 'Load skills with Skill; read with Read; write/edit with Write/Edit; shell with Bash. Use Agent only when authorized.',
    'codex': 'Load the listed skill instructions; read/run with exec_command; modify with apply_patch. Use host agent tools only when authorized.',
    'opencode': 'Load skills with skill; read with read; modify with patch (patchText), write/edit; commands with shell. Use subagent only when authorized; keep tasks.md as the sole task plan.',
    'dsh': 'Use the integrating host native skill/file/shell tools. Missing capabilities must be reported, never invented.',
}


@lru_cache(maxsize=8)
def _static_contract(root: str) -> str:
    candidates = [Path(root) / 'skills/development-workflow/references/bootstrap.md',
                  Path(sys.prefix) / 'share/wm-ai-coding/bootstrap.md']
    for path in candidates:
        if path.is_file():
            return path.read_text(encoding='utf-8').strip()
    raise ValueError('WM bootstrap.md missing from installed plugin/runtime')


def startup(host: str, payload: dict) -> str:
    parent = payload.get('parent_session_id') or payload.get('parentID')
    if parent:
        return ('<WM_WORKER>Follow the assigned parent task, handoff and scope; do not restart '
                'requirements or approval. Load needed skills explicitly. Parent: '
                f'{parent}</WM_WORKER>')
    return (_static_contract(str(plugin_root())) + '\nTool mapping: ' + MAPPINGS[host]
            + '\nInstalled plugin root: ' + str(plugin_root()))


def context_output(host: str, event: str, content: str) -> dict:
    if host in {'dsh', 'opencode'}:
        return {'context': content}
    return {'hookSpecificOutput': {'hookEventName': event, 'additionalContext': content}}
