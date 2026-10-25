"""Read-only release validation and optional local MCP protocol handshakes."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from wm_ai_coding.identity import VERSION, verify_bundle
from wm_ai_coding.registry import validate_registry


def check(root: Path, *, mcp: bool = False) -> dict:
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
                    process=subprocess.run([sys.executable,str(root/'scripts/mcp_launcher.py'),name,*args],
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


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--mcp',action='store_true');args=parser.parse_args()
    result=check(Path(__file__).resolve().parents[1],mcp=args.mcp)
    print(json.dumps(result,indent=2));raise SystemExit(0 if result['valid'] else 1)
