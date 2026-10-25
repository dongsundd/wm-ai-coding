"""Host adapters: supported tool guardrails, never a replacement for a sandbox."""
from __future__ import annotations

import json
import re
import shlex
from pathlib import Path

from wm_ai_coding.evidence.runs import load_plan

CAPABILITIES = {
    "codex": {"events": ["SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop", "PreCompact", "PostCompact"],
              "limits": ["hook trust required", "hosted/specialized tools may bypass hooks", "existing shell sessions are not rechecked"]},
    "claude": {"events": ["SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop", "PreCompact"],
               "limits": ["shell children/external writes need sandbox and return inventory"]},
    "dsh": {"events": ["session-start", "pre-tool-use", "post-tool-use", "stop"],
            "limits": ["bridge requires host plugin integration; no bundled model loop"]},
}


def decision(host: str, allowed: bool, reason: str) -> dict:
    if host == "dsh":
        return {"allowed": allowed, "reason": reason}
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow" if allowed else "deny",
                                   "permissionDecisionReason": reason}}


def handle_hook(machine, host: str, event: str, payload: dict) -> dict:
    if host not in CAPABILITIES or event not in CAPABILITIES[host]["events"]:
        raise ValueError("unsupported host/event")
    from wm_ai_coding.infrastructure.diagnostics import brief
    state = machine.status()
    name = payload.get("change") or state.get("active_change")
    item = state.get("changes", {}).get(name)
    if event in {"SessionStart", "UserPromptSubmit", "PreCompact", "PostCompact", "session-start"}:
        content = json.dumps(brief(machine, name), ensure_ascii=False) if item else "WM: no active change; development requests enter development-workflow."
        if host == "dsh":
            return {"context": content}
        return {"hookSpecificOutput": {"hookEventName": event, "additionalContext": content}}
    if event in {"Stop", "stop"}:
        # Hosts do not uniformly provide completion intent. Pausing is always legal.
        claims = payload.get("intent") == "complete" or payload.get("completion_claim") is True
        if claims and item and (item.get("status") != "archived" or not item.get("integrity", {}).get("valid")):
            return {"decision": "block", "reason": "WM completion claim lacks verified archive; pause or report remaining work."}
        return {}
    if event in {"PostToolUse", "post-tool-use"}:
        return {"systemMessage": "WM: record command evidence; finish-handoff also checks actual file changes."} if item else {}
    if not item:
        return {}  # No unrelated-project policy is installed implicitly.
    handoff = item.get("last_handoff") or {}
    tool = payload.get("tool_name", "")
    args = payload.get("tool_input", {})
    if not isinstance(args, dict):
        return decision(host, False, "invalid tool input")
    path_value = args.get("file_path") or args.get("path")
    writes = tool in {"Write", "Edit", "apply_patch"} or bool(re.search(r"(?:write|edit|delete|move|patch)", tool, re.I))
    if tool == "apply_patch":
        paths = re.findall(r"(?m)^\*\*\* (?:Add File|Update File|Delete File|Move to): (.+)$", args.get("command", args.get("patch", "")))
        if not paths:
            return decision(host, False, "cannot determine patch targets")
    else:
        paths = [path_value] if path_value else []
    if writes:
        if handoff.get("status") != "running" or not paths:
            return decision(host, False, "write needs a running scoped handoff and explicit targets")
        for value in paths:
            path = (machine.repo / value).resolve()
            if path.is_relative_to(machine.repo / ".wm"):
                return decision(host, False, "use wm controller commands for runtime state")
            if not any(path.is_relative_to((machine.repo / scope).resolve()) for scope in handoff["scope"]):
                return decision(host, False, "write outside active handoff scope")
        return decision(host, True, "targets inside declared scope; host sandbox remains authoritative")
    if tool in {"Bash", "PowerShell", "exec_command"}:
        command = args.get("command", args.get("cmd", ""))
        try:
            words = shlex.split(command, posix=True)
        except ValueError:
            return decision(host, False, "cannot parse shell command; use a declared argv check")
        if any(token in command for token in (";", "\n", "&&", "||", "|", ">", "<", "`", "$(")):
            return decision(host, False, "compound shell command requires host review; use declared checks")
        # A literal WM controller invocation is allowed; never match by substring.
        controller = (words and Path(words[0]).name.lower() in {"wm", "wm.exe"})
        if len(words) > 1 and Path(words[0]).name.lower() in {"python", "python3", "python.exe"}:
            wrapper = Path(words[1]).resolve()
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
        allowed = handoff.get("status") == "running" and any(words == c["argv"] for c in checks)
        return decision(host, allowed, "declared check" if allowed else "undeclared shell operation; declare a check or obtain host authorization")
    return {}
