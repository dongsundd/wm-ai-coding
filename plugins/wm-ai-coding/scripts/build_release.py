"""Generate host manifests and seal one immutable release bundle."""
from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wm_ai_coding.identity import VERSION, seal_bundle


def build(root: Path):
    legacy = root / ".codex-plugin/plugin.json"
    data = json.loads(legacy.read_text(encoding="utf-8"))
    data["version"] = VERSION
    data["hooks"] = "./hooks/codex.json"
    legacy.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    portable = {"$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json", "name": "wm-ai-coding",
                "version": VERSION, "description": data["description"],
                "extensions": {"com.openai": {"hooks": "./hooks/codex.json", "interface": data["interface"]}}}
    (root / "plugin.json").write_text(json.dumps(portable, indent=2, ensure_ascii=False)+"\n", encoding="utf-8", newline="\n")
    claude = root / ".claude-plugin/plugin.json";claude.parent.mkdir(exist_ok=True)
    claude.write_text(json.dumps({"name": "wm-ai-coding", "version": VERSION, "description": data["description"], "author": data["author"],
                                 "skills": "./skills/", "hooks": "./hooks/claude.json", "mcpServers": "./.mcp.json"},indent=2,ensure_ascii=False)+"\n",encoding="utf-8", newline="\n")
    hooks = root / "hooks"; hooks.mkdir(exist_ok=True)
    for host, filename, variable in [("codex","codex.json","PLUGIN_ROOT"),("claude","claude.json","CLAUDE_PLUGIN_ROOT")]:
        events=["SessionStart","UserPromptSubmit","PreToolUse","PostToolUse","Stop","PreCompact"]
        if host=="codex":events.append("PostCompact")
        config={"hooks":{event:[{"hooks":[{"type":"command","command":f'python "${{{variable}}}/scripts/wm_hook.py" {host} {event}',"timeout":10}]}] for event in events}}
        (hooks/filename).write_text(json.dumps(config,indent=2)+"\n",encoding="utf-8", newline="\n")
    portable_mcp = json.loads((root / ".mcp.json").read_text(encoding="utf-8"))
    portable_mcp["$schema"] = "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json"
    for server in portable_mcp["mcpServers"].values(): server["type"] = "stdio"
    (root / "mcp.json").write_text(json.dumps(portable_mcp, indent=2)+"\n", encoding="utf-8", newline="\n")
    return seal_bundle(root)


if __name__ == "__main__":
    print(json.dumps({k:v for k,v in build(Path(__file__).resolve().parents[1]).items() if k != "files"}))
