"""Generate and verify host distribution files."""
from __future__ import annotations
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
from wm_ai_coding.infrastructure.identity import VERSION, seal_bundle, verify_bundle
from wm_ai_coding.infrastructure.registry import validate_registry


def build(root: Path):
    legacy = root / ".codex-plugin/plugin.json"
    data = json.loads((root / 'metadata.json').read_text(encoding="utf-8"))
    data["version"] = VERSION
    data['skills'] = './skills/'
    data['mcpServers'] = './.codex.mcp.json'
    data["hooks"] = "./hooks/codex.json"
    legacy.parent.mkdir(exist_ok=True)
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
        events.append('SubagentStart')
        config={"hooks":{event:[{"hooks":[{"type":"command","command":f'python "${{{variable}}}/scripts/wm.py" hook {host} {event}',"timeout":10}]}] for event in events}}
        (hooks/filename).write_text(json.dumps(config,indent=2)+"\n",encoding="utf-8", newline="\n")
    # The Python entrypoint and server arguments are shared; root expansion is host-owned.
    servers = {
        'codegraph': {'command': 'python', 'args': ['ROOT/scripts/wm.py', 'mcp', 'codegraph', 'serve', '--mcp'],
                      'env': {'CODEGRAPH_MCP_TOOLS': 'explore,node,search,callers,callees,impact,files,status'}},
        'playwright': {'command': 'python', 'args': ['ROOT/scripts/wm.py', 'mcp', 'playwright-mcp',
                       '--isolated', '--headless', '--codegen=none', '--block-service-workers']},
    }
    for filename, variable in [('.mcp.json', '${CLAUDE_PLUGIN_ROOT}'), ('.codex.mcp.json', '${PLUGIN_ROOT}')]:
        config = json.loads(json.dumps({'mcpServers': servers}).replace('ROOT/scripts', variable + '/scripts'))
        if filename == '.codex.mcp.json':
            # Native compatibility manifests do not interpolate root variables.
            # Codex resolves relative cwd against the installed plugin root.
            for server in config['mcpServers'].values():
                server['args'][0] = 'scripts/wm.py'
                server['cwd'] = './'
        (root / filename).write_text(json.dumps(config, indent=2) + '\n', encoding='utf-8', newline='\n')
    package = root / '.opencode/plugins/wm-ai-coding/package.json'
    info = json.loads(package.read_text(encoding='utf-8'))
    info['version'] = VERSION
    package.write_text(json.dumps(info, indent=2) + '\n', encoding='utf-8', newline='\n')
    portable_mcp = json.loads(json.dumps({'mcpServers': servers}).replace('ROOT/scripts', '${PLUGIN_ROOT}/scripts'))
    portable_mcp["$schema"] = "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json"
    for server in portable_mcp["mcpServers"].values(): server["type"] = "stdio"
    (root / "mcp.json").write_text(json.dumps(portable_mcp, indent=2)+"\n", encoding="utf-8", newline="\n")
    return seal_bundle(root)


def package(root: Path, host: str, output: Path) -> dict:
    """Materialize a sealed native-host bundle without changing shared sources."""
    if host not in {'codex', 'claude', 'opencode'}:
        raise ValueError('unsupported distribution host')
    root, output = root.resolve(), output.resolve()
    if output.exists() or root.is_relative_to(output):
        raise ValueError('package output must be a new directory, separate from source')
    if output.is_relative_to(root) and output.relative_to(root).parts[0] != 'dist':
        raise ValueError('outputs inside the source bundle must be under dist/')
    source = verify_bundle(root)
    if not source['valid']:
        raise ValueError('source bundle is not sealed; run release build first')
    if any(path.is_symlink() for path in root.rglob('*')):
        raise ValueError('release packaging does not follow source symlinks')
    shutil.copytree(root, output, ignore=shutil.ignore_patterns(
        '.git', '__pycache__', '.pytest_cache', '.venv', 'build', 'dist', '*.egg-info'))
    if host == 'codex':
        # Codex 0.164 prioritizes plugin.json but does not discover its extension
        # hooks. Its native package must select the compatibility manifest.
        (output / 'plugin.json').unlink(missing_ok=True)
    distribution = {'host': host, 'version': VERSION, 'source_digest': source['digest']}
    (output / 'distribution.json').write_text(json.dumps(distribution, indent=2) + '\n', encoding='utf-8')
    sealed = seal_bundle(output)
    return {**distribution, 'path': str(output), 'digest': sealed['digest']}


def verify(root: Path, *, mcp: bool = False) -> dict:
    findings=validate_registry(root)
    release=verify_bundle(root)
    if not release['valid']:findings.append('bundle content differs from release manifest')
    distribution_path = root / 'distribution.json'
    distribution = json.loads(distribution_path.read_text(encoding='utf-8')) if distribution_path.is_file() else {}
    paths = ['.codex-plugin/plugin.json','.claude-plugin/plugin.json']
    if distribution.get('host') == 'codex':
        if (root/'plugin.json').exists():findings.append('portable manifest shadows native Codex hooks')
    else:
        paths.insert(0,'plugin.json')
    manifests=[json.loads((root/path).read_text(encoding='utf-8')) for path in paths]
    if any(m['version']!=VERSION for m in manifests):findings.append('manifest version mismatch')
    package = json.loads((root / '.opencode/plugins/wm-ai-coding/package.json').read_text(encoding='utf-8'))
    if package.get('version') != VERSION: findings.append('OpenCode package version mismatch')
    for filename, variable in [('.mcp.json', '${CLAUDE_PLUGIN_ROOT}'), ('.codex.mcp.json', '${PLUGIN_ROOT}')]:
        config = json.loads((root / filename).read_text(encoding='utf-8'))
        if any((server['args'][0] != 'scripts/wm.py' or server.get('cwd') != './')
               if filename == '.codex.mcp.json' else not server['args'][0].startswith(variable + '/')
               for server in config['mcpServers'].values()):
            findings.append(f'{filename}: invalid host root variable')
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


