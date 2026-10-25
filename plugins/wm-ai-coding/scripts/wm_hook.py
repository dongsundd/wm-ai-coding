"""Thin executable bridge. Host owns hook trust, permissions and event delivery."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wm_ai_coding.cli import workflow_path
from wm_ai_coding.workflow import load_workflow
from wm_ai_coding.machine import StateMachine
from wm_ai_coding.hooks import handle_hook, decision


def main():
    host, event = sys.argv[1:3]
    try:
        payload = json.load(sys.stdin)
        cwd = Path(payload.get("cwd", Path.cwd())).resolve()
        repo = next((p for p in (cwd, *cwd.parents) if (p / ".wm/state.json").is_file()), None)
        if repo is None:
            result = {"hookSpecificOutput": {"hookEventName": event, "additionalContext":
                "WM: development work enters development-workflow; initialize explicitly with wm init --no-gitignore."}} if event in {"SessionStart", "UserPromptSubmit"} else {}
        else:
            result = handle_hook(StateMachine(repo, load_workflow(workflow_path())), host, event, payload)
    except Exception as exc:
        result = decision(host, False, f"WM hook error: {exc}") if event == "PreToolUse" else {"systemMessage": f"WM hook error: {exc}"}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
