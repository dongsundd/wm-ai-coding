"""Generate and verify host distribution files."""
from __future__ import annotations
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from wm_ai_coding.infrastructure.identity import VERSION, seal_bundle, verify_bundle
from wm_ai_coding.infrastructure.registry import validate_registry


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
        config={"hooks":{event:[{"hooks":[{"type":"command","command":f'python "${{{variable}}}/scripts/wm.py" hook {host} {event}',"timeout":10}]}] for event in events}}
        (hooks/filename).write_text(json.dumps(config,indent=2)+"\n",encoding="utf-8", newline="\n")
    portable_mcp = json.loads((root / ".mcp.json").read_text(encoding="utf-8"))
    portable_mcp["$schema"] = "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json"
    for server in portable_mcp["mcpServers"].values(): server["type"] = "stdio"
    (root / "mcp.json").write_text(json.dumps(portable_mcp, indent=2)+"\n", encoding="utf-8", newline="\n")
    return seal_bundle(root)


def verify(root: Path, *, mcp: bool = False) -> dict:
    findings=validate_registry(root)
    release=verify_bundle(root)
    if not release['valid']:findings.append('bundle content differs from release manifest')
    manifests=[json.loads((root/path).read_text(encoding='utf-8')) for path in
               ('plugin.json','.codex-plugin/plugin.json','.claude-plugin/plugin.json')]
    if any(m['version']!=VERSION for m in manifests):findings.append('manifest version mismatch')
    if (root/'hooks/hooks.json').exists():findings.append('ambiguous default hooks would load on multiple hosts')
    for host in ('codex','claude'):
        hooks=json.loads((root/f'hooks/{host}.json').read_text(encoding='utf-8'))['hooks']
        for event,groups in hooks.items():
            for group in groups:
                for hook in group['hooks']:
                    if f'{host} {event}' not in hook['command']:findings.append('hook host/event mismatch')
    handshakes={}
    if mcp:
        for name,args in [('codegraph',['serve','--mcp']),('playwright-mcp',['--isolated','--headless','--codegen=none','--block-service-workers'])]:
            messages=[{'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2024-11-05','capabilities':{},'clientInfo':{'name':'wm-release-smoke','version':VERSION}}},
                      {'jsonrpc':'2.0','method':'notifications/initialized'},
                      {'jsonrpc':'2.0','id':2,'method':'tools/list','params':{}}]
            env=dict(os.environ);env['CODEGRAPH_MCP_TOOLS']='explore,node,search,callers,callees,impact,files,status'
            with tempfile.TemporaryFile() as errors:
                try:
                    process=subprocess.run([sys.executable,str(root/'scripts/wm.py'),'mcp',name,*args],
                        input=''.join(json.dumps(x)+'\n' for x in messages),text=True,encoding='utf-8',errors='replace',stdout=subprocess.PIPE,stderr=errors,
                        timeout=25,env=env,check=False)
                    responses=[json.loads(line) for line in process.stdout.splitlines() if line.startswith('{')]
                    initialized=any(r.get('id')==1 and 'result' in r for r in responses)
                    tools=next((r.get('result',{}).get('tools',[]) for r in responses if r.get('id')==2),[])
                    handshakes[name]={'initialized':initialized,'tools':len(tools),'exit_code':process.returncode}
                    if not initialized or not tools:findings.append(f'{name}: MCP handshake/tools failed')
                except (OSError,ValueError,subprocess.TimeoutExpired) as exc:
                    findings.append(f'{name}: {exc}')
    return {'valid':not findings,'release':release,'findings':findings,'handshakes':handshakes,
            'host_loading':'native manifest/protocol checks do not prove hook trust or live session activation'}


