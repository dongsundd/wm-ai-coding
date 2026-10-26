"""Host adapters: supported tool guardrails, never a replacement for a sandbox."""
from __future__ import annotations

import json
import shlex
from pathlib import Path

from wm_ai_coding.evidence.runs import load_plan
from .bootstrap import startup, context_output
from .host_tools import normalize_tool

CAPABILITIES = {
    "codex": {"events": ["SessionStart", "SubagentStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop", "PreCompact", "PostCompact"],
              "limits": ["hook trust required", "hosted/specialized tools may bypass hooks", "existing shell sessions are not rechecked"]},
    "claude": {"events": ["SessionStart", "SubagentStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop", "PreCompact"],
               "limits": ["shell children/external writes need sandbox and return inventory"]},
    "dsh": {"events": ["session-start", "pre-tool-use", "post-tool-use", "stop"],
            "limits": ["bridge requires host plugin integration; no bundled model loop"]},
    "opencode": {"events": ["context", "PreToolUse", "PostToolUse", "Stop"],
                 "limits": ["OpenCode v2 native plugin required", "host permissions remain authoritative"]},
}


def decision(host: str, allowed: bool, reason: str) -> dict:
    if host in {"dsh", "opencode"}:
        return {"allowed": allowed, "reason": reason}
    if host == 'claude' and allowed:
        # Silence defers to Claude's permission flow; "allow" would grant permission.
        return {}
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow" if allowed else "deny",
                                   "permissionDecisionReason": reason}}


def handle_hook(machine, host: str, event: str, payload: dict) -> dict:
    if host not in CAPABILITIES or event not in CAPABILITIES[host]["events"]:
        raise ValueError("unsupported host/event")
    from wm_ai_coding.infrastructure.diagnostics import brief
    state = machine.status()
    name = payload.get("change") or state.get("active_change")
    item = state.get("changes", {}).get(name)
    if event == 'PreCompact' or (host == 'codex' and event == 'PostCompact'):
        # Restore via SessionStart(source=compact), whose output is consumed as context.
        return {}
    if event in {"SessionStart", "SubagentStart", "UserPromptSubmit", "PreCompact", "PostCompact", "session-start", "context"}:
        content = json.dumps(brief(machine, name), ensure_ascii=False) if item else "WM: no active change; development requests enter development-workflow."
        if event in {'SessionStart', 'SubagentStart', 'session-start', 'context'}:
            content = startup(host, payload) + '\nWM current state: ' + content
            if payload.get('parent_session_id') or payload.get('parentID'):
                assignment = (item or {}).get('last_handoff') or {}
                content += '\nWM assigned handoff: ' + json.dumps({
                    key:assignment.get(key) for key in ('id','status','task','scope')
                }, ensure_ascii=False)
        return context_output(host, event, content)
    if event in {"Stop", "stop"}:
        if payload.get('stop_hook_active') is True:
            return {}
        # Hosts do not uniformly provide completion intent. Pausing is always legal.
        claims = payload.get("intent") == "complete" or payload.get("completion_claim") is True
        if claims and item and (item.get("status") != "archived" or not item.get("integrity", {}).get("valid")):
            return {"decision": "block", "reason": "WM completion claim lacks verified archive; pause or report remaining work."}
        return {}
    if event in {"PostToolUse", "post-tool-use"}:
        return context_output(host, event, 'WM: record command evidence; finish-handoff also checks actual file changes.') if item else {}
    if not item:
        return {}  # No unrelated-project policy is installed implicitly.
    handoff = item.get("last_handoff") or {}
    try:
        operation = normalize_tool(payload, machine.repo)
    except (ValueError, OSError) as exc:
        return decision(host, False, str(exc))
    if operation.kind == 'write':
        if handoff.get("status") != "running":
            return decision(host, False, "write needs a running scoped handoff and explicit targets")
        for path in operation.targets:
            if path.is_relative_to(machine.repo / ".wm"):
                return decision(host, False, "use wm controller commands for runtime state")
            if not any(path.is_relative_to((machine.repo / scope).resolve()) for scope in handoff["scope"]):
                return decision(host, False, "write outside active handoff scope")
        return decision(host, True, "targets inside declared scope; host sandbox remains authoritative")
    if operation.kind == 'shell':
        command = operation.command
        try:
            words = shlex.split(command, posix=True)
        except ValueError:
            return decision(host, False, "cannot parse shell command; use a declared argv check")
        if any(token in command for token in (";", "\n", "\r", "&", "||", "|", ">", "<", "`", "$(")):
            return decision(host, False, "split read-only inspections into single commands; use declared checks for compound operations")
        readonly = {'get-content','get-childitem','get-location','pwd','cat','ls','head','tail','rg'}
        executable = Path(words[0]).name.lower() if words else ''
        if executable in readonly and not any(token in command for token in ('(',')','{','}','$','\x00')):
            if executable != 'rg' or not any(word.startswith(('--pre','--hostname-bin')) for word in words[1:]):
                return {}  # Read-only inspection defers to the normal host permission flow.
        # A literal WM controller invocation is allowed; never match by substring.
        controller = (words and Path(words[0]).name.lower() in {"wm", "wm.exe"})
        if len(words) > 1 and Path(words[0]).name.lower() in {"python", "python3", "python.exe"}:
            wrapper = (operation.workdir / words[1]).resolve()
            from ..infrastructure.paths import plugin_root
            root = plugin_root()
            expected = (root / "scripts/wm.py", root / "skills/development-workflow/scripts/harness_state.py")
            controller = wrapper in {path.resolve() for path in expected}
        if controller:
            return decision(host, True, "WM controller enforces its own gates; host permissions still apply")
        try:
            checks = load_plan(machine._change_path(name))
        except ValueError:
            checks = []
        allowed = (handoff.get("status") == "running" and operation.workdir == machine.repo
                   and any(words == c["argv"] for c in checks))
        return decision(host, allowed, "declared check" if allowed else "undeclared shell operation; declare a check or obtain host authorization")
    return {}
