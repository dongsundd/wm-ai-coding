"""Run installed host plugins and retain evidence; incomplete suites fail closed.

This is a local acceptance record, not authenticated attestation. It never accepts
a supplied `passed` flag as proof of a native host execution.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import uuid
import queue
import threading
import time
import shlex
from contextlib import contextmanager

PLUGIN = Path(__file__).resolve().parents[3]
REPO = PLUGIN.parents[1]
REQUIRED = {'route-1', 'route-2', 'route-3', 'read-only', 'scope', 'failure', 'resume', 'compact', 'worker', 'mcp'}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def validate_installation(root):
    sys.path.insert(0,str(PLUGIN/'scripts'))
    from wm_ai_coding.infrastructure.identity import verify_bundle
    try:
        return verify_bundle(root)['valid']
    except (OSError, ValueError, KeyError):
        return False


def events(path):
    result = []
    if Path(path).is_file():
        for line in Path(path).read_text(encoding='utf-8', errors='replace').splitlines():
            try:
                value = json.loads(line)
                if isinstance(value, dict):
                    result.append(value)
            except ValueError:
                continue
    return result


def tool_calls(records):
    """Read native tool invocations, not claims in assistant prose."""
    found = []
    def visit(value):
        if isinstance(value, dict):
            if value.get('type') in {'tool_use', 'tool_call', 'tool', 'function_call'}:
                found.append((value.get('name') or value.get('tool') or '', value.get('input', value.get('state', {}))))
            if value.get('type') == 'command_execution':
                found.append(('shell', value.get('command', '')))
            if value.get('type') == 'mcp_tool_call':
                found.append((str(value.get('server','')) + '__' + str(value.get('tool','')), value.get('arguments',{})))
            if value.get('type') == 'collab_tool_call':
                found.append((value.get('tool',''), value.get('prompt','')))
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    visit(records)
    return found


def routed(records):
    for name, arguments in tool_calls(records):
        if ('skill' in name.lower() or name.lower() in {'shell', 'bash', 'exec_command', 'read'}) and 'development-workflow' in json.dumps(arguments):
            return True
    return False


def session_id(records):
    for record in records:
        value = record.get('session_id') or record.get('sessionID') or record.get('thread_id')
        if value:
            return value
    return None


def native_checks(scenario, project, records, hooks):
    calls = tool_calls(records)
    if scenario == 'scope':
        inside = project / 'allowed/inside.txt'
        outside = project / 'outside.txt'
        return (inside.is_file() and outside.is_file() and inside.read_text(encoding='utf-8').rstrip('\r\n') == 'WM_SCOPE_OK'
                and outside.read_text(encoding='utf-8') == 'untouched'
                and any(h.get('allowed') is False or h.get('permissionDecision') == 'deny' for h in hooks))
    if scenario == 'resume':
        return any(h.get('state', {}).get('stage') == 'apply' and h.get('state', {}).get('task') == 'task-1'
                   and h.get('state', {}).get('status') == 'blocked' for h in hooks)
    if scenario == 'failure':
        state_file = project/'.wm/state.json'
        if not state_file.is_file(): return False
        state = json.loads(state_file.read_text(encoding='utf-8'))['changes']['c1']
        failed = []
        for path in (project/'.wm/runs').rglob('*.json'):
            try: data=json.loads(path.read_text(encoding='utf-8'))
            except ValueError: continue
            if data.get('exit_code') == 3: failed.append(path)
        return bool(failed) and state.get('stage') == 'apply' and not state.get('task_receipts')
    if scenario == 'compact':
        for index,hook in enumerate(hooks):
            if hook.get('source')=='compact' or hook.get('event')=='PostCompact':
                if any(next_hook.get('state',{}).get('stage')=='apply' and next_hook.get('state',{}).get('task')=='task-1'
                       for next_hook in hooks[index+1:]):return True
        return False
    if scenario == 'worker':
        spawned=any(name.lower() in {'agent','subagent','task','spawn_agent'} for name, _ in calls)
        spawned=spawned or any(h.get('event')=='PostToolUse' and h.get('tool') in {
            'spawn_agent','collaborationspawn_agent','Agent','subagent','task'} for h in hooks)
        return any(h.get('worker') for h in hooks) and spawned
    if scenario == 'mcp':
        # Invocation and successful native result are both required.
        success = set()
        identities = {}
        def inspect(value):
            if isinstance(value, dict):
                kind = value.get('type')
                if kind == 'tool_use':
                    identities[value.get('id')] = value.get('name','')
                if kind == 'tool_result' and not value.get('is_error',False):
                    name = identities.get(value.get('tool_use_id'),'').lower()
                    for server in ('codegraph','playwright'):
                        if server in name: success.add(server)
                if kind == 'tool' and value.get('state',{}).get('status') == 'completed':
                    for server in ('codegraph','playwright'):
                        if server in value.get('tool','').lower(): success.add(server)
                if (kind == 'mcp_tool_call' and value.get('status') == 'completed' and not value.get('error')
                        and isinstance(value.get('result'),dict) and not value['result'].get('isError',False)):
                    for server in ('codegraph','playwright'):
                        if server in value.get('server','').lower(): success.add(server)
                for child in value.values(): inspect(child)
            elif isinstance(value,list):
                for child in value: inspect(child)
        inspect(records)
        return success == {'codegraph','playwright'} and 'about:blank' in json.dumps(calls)
    return False


def assess(directory: Path, expected_digest: str) -> dict:
    findings = []
    manifest_path = directory / 'manifest.json'
    if not manifest_path.is_file():
        return {'passed': False, 'findings': ['manifest missing'], 'routing': '0/3'}
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest.get('bundle_digest') != expected_digest:
        findings.append('bundle digest mismatch')
    if manifest.get('mock') is not False:
        findings.append('native execution evidence required; mock or unspecified origin')
    if not manifest.get('host_version'):
        findings.append('host version missing')
    if not manifest.get('model'):
        findings.append('model identity missing')
    sessions = manifest.get('sessions', [])
    observed = set()
    routing = 0
    for session in sessions:
        scenario = session.get('scenario')
        if scenario in observed:
            findings.append(f'duplicate scenario: {scenario}')
            continue
        observed.add(scenario)
        transcript = directory / session.get('transcript', '__missing__')
        trace = directory / session.get('trace', '__missing__')
        if not transcript.resolve().is_relative_to(directory.resolve()) or not trace.resolve().is_relative_to(directory.resolve()):
            findings.append(f'{scenario}: evidence path escapes run')
            continue
        if not transcript.is_file() or not trace.is_file():
            findings.append(f'{scenario}: transcript/trace missing')
            continue
        if session.get('transcript_sha256') != digest(transcript) or session.get('trace_sha256') != digest(trace):
            findings.append(f'{scenario}: evidence digest mismatch')
            continue
        records, hooks = events(transcript), events(trace)
        if any(record.get('type') in {'error', 'turn.failed'} or record.get('is_error') is True for record in records):
            findings.append(f'{scenario}: native provider/session error')
            continue
        if session.get('exit_code') != 0 or not records or not hooks:
            findings.append(f'{scenario}: host failed or no native event evidence')
            continue
        if scenario.startswith('route-'):
            if routed(records) and any(e.get('bootstrap') for e in hooks) and not session.get('product_files_changed'):
                routing += 1
            else:
                findings.append(f'{scenario}: workflow routing before product writes not demonstrated')
        elif scenario == 'read-only':
            if session.get('state_created') or session.get('product_files_changed'):
                findings.append('read-only: modified project state/files')
        else:
            # Scenario-specific native evidence is required. A model's claim is insufficient.
            project = directory / session.get('project', '__missing__')
            if not project.resolve().is_relative_to(directory.resolve()) or not native_checks(scenario, project, records, hooks):
                findings.append(f'{scenario}: required native tool/state observations not met')
    missing = REQUIRED - observed
    if missing:
        findings.append('missing scenarios: ' + ', '.join(sorted(missing)))
    if routing != 3:
        findings.append(f'fresh-session routing requires 3/3; observed {routing}/3')
    return {'passed': not findings, 'findings': findings, 'routing': f'{routing}/3'}


def executable(host):
    command = shutil.which(host)
    if not command:
        raise FileNotFoundError(f'{host} not installed')
    if os.name == 'nt' and Path(command).suffix.lower() in {'.cmd', '.ps1'}:
        # Resolve npm wrappers to native/Node entrypoints; never shell-parse prompts.
        base = Path(command).parent
        native = {
            'claude': base / 'node_modules/@anthropic-ai/claude-code/bin/claude.exe',
            'opencode': base / 'node_modules/@opencode/cli/bin/opencode.exe',
        }.get(host)
        if native and native.is_file():
            return [str(native)]
        script = base / 'node_modules/@openai/codex/bin/codex.js'
        if host == 'codex' and script.is_file():
            return [shutil.which('node') or 'node', str(script)]
        raise ValueError(f'cannot resolve native {host} entrypoint from {command}')
    return [command]


def execute(argv, cwd, env, stdout, stderr, timeout):
    with Path(stdout).open('wb') as out, Path(stderr).open('wb') as err:
        process = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=err)
        try:
            return process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            if os.name == 'nt':
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True, timeout=15)
            else:
                process.kill()
            process.wait(timeout=15)
            return 124


@contextmanager
def codex_control(binary, cwd, env, stdout, stderr, timeout):
    """Bounded native control channel shared by inspection and compaction."""
    with Path(stdout).open('w',encoding='utf-8') as output, Path(stderr).open('w',encoding='utf-8') as errors:
        process=subprocess.Popen(binary+['--dangerously-bypass-hook-trust','app-server','--enable','hooks'],
            cwd=cwd,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=errors,
            text=True,encoding='utf-8')
        pending=queue.Queue()
        def read():
            for line in process.stdout:
                try: pending.put(json.loads(line))
                except ValueError: continue
        reader=threading.Thread(target=read,daemon=True)
        reader.start()
        deadline=time.monotonic()+timeout
        def send(value):
            process.stdin.write(json.dumps(value)+'\n');process.stdin.flush()
        def until(predicate):
            while True:
                remaining=deadline-time.monotonic()
                if remaining <= 0:
                    raise queue.Empty
                value=pending.get(timeout=remaining)
                output.write(json.dumps(value,ensure_ascii=True)+'\n');output.flush()
                if 'error' in value:
                    raise RuntimeError('native compaction control request failed')
                if predicate(value):return value
        try:
            send({'id':1,'method':'initialize','params':{'clientInfo':{'name':'wm-compact-acceptance','version':'0.9.1'},'capabilities':{'experimentalApi':True}}})
            until(lambda value:value.get('id')==1)
            send({'method':'initialized'})
            yield send,until
        finally:
            if process.poll() is None:
                if os.name=='nt':
                    subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True,timeout=15)
                else:
                    process.terminate()
            process.wait(timeout=15)
            if process.stdin:process.stdin.close()
            if process.stdout:process.stdout.close()
            reader.join(timeout=1)


def codex_compact(binary, thread, cwd, env, stdout, stderr, timeout):
    """Request real compaction; an exec prompt containing /compact is not enough."""
    try:
        with codex_control(binary,cwd,env,stdout,stderr,timeout) as (send,until):
            send({'id':2,'method':'thread/resume','params':{'threadId':thread,'cwd':str(cwd),'sandbox':'danger-full-access','approvalPolicy':'never'}})
            until(lambda value:value.get('id')==2)
            send({'id':3,'method':'thread/compact/start','params':{'threadId':thread}})
            until(lambda value:value.get('method')=='thread/compacted' or (
                value.get('method')=='item/completed' and value.get('params',{}).get('item',{}).get('type')=='contextCompaction'))
            post=until(lambda value:value.get('method')=='hook/completed'
                       and value.get('params',{}).get('run',{}).get('eventName')=='postCompact')
            if post['params']['run'].get('status')!='completed':
                raise RuntimeError('native PostCompact hook failed')
        return 0
    except queue.Empty:
        with Path(stderr).open('a',encoding='utf-8') as errors:errors.write('Native compaction timed out\n')
        return 124
    except (OSError,RuntimeError) as exc:
        with Path(stderr).open('a',encoding='utf-8') as errors:errors.write(str(exc)+'\n')
        return 1


def trust_codex_hooks(binary, cwd, env, installed, stdout, stderr, timeout):
    """Trust only this vetted bundle's hashes in the disposable native home."""
    config=Path(env['CODEX_HOME']).resolve()
    if not config.is_relative_to(Path(tempfile.gettempdir()).resolve()) or not config.name.startswith('wm-host-config-'):
        raise ValueError('hook trust may only be written to the disposable acceptance home')
    with codex_control(binary,cwd,env,stdout,stderr,timeout) as (send,until):
        send({'id':2,'method':'hooks/list','params':{'cwds':[str(cwd)]}})
        response=until(lambda value:value.get('id')==2)
    approved=[]
    for entry in response['result']['data']:
        for hook in entry.get('hooks',[]):
            if hook.get('pluginId')!='wm-ai-coding@wm-acceptance':continue
            words=shlex.split(hook.get('command',''))
            if (len(words)!=5 or words[0] not in {'python','python3','python.exe'}
                    or Path(words[1]).resolve()!=(installed/'scripts/wm.py').resolve()
                    or words[2:4]!=['hook','codex']):
                raise ValueError('refusing to trust an unexpected native hook command')
            value=hook.get('currentHash','')
            if not re.fullmatch(r'sha256:[0-9a-f]{64}/sha256:[0-9a-f]{64}',value):
                raise ValueError('native hook has no valid declaration/content hash')
            declaration,content=value.split('/')
            approved.append((hook['key'],declaration,content))
    if not approved:raise ValueError('native Codex did not discover any WM hooks')
    with (config/'config.toml').open('a',encoding='utf-8') as stream:
        for key,declaration,content in approved:
            stream.write('\n[hooks.state.'+json.dumps(key)+']\nenabled = true\ntrusted_hash = '+json.dumps(declaration)
                         +'\ntrusted_content_hash = '+json.dumps(content)+'\n')


def snapshot(project):
    return {str(p.relative_to(project)): digest(p) for p in project.rglob('*') if p.is_file()
            and not any(part in {'.git', '.wm', 'sdd', '.opencode', '.claude', '.codex'} for part in p.relative_to(project).parts)
            and p.name != 'opencode.json'}


def codex_settings(previous):
    """Keep the selected native model/provider only, in the disposable home."""
    def value(item):
        if isinstance(item, dict):
            return '{' + ', '.join(json.dumps(k) + ' = ' + value(v) for k,v in item.items()) + '}'
        if isinstance(item, list):
            return '[' + ', '.join(value(v) for v in item) + ']'
        if isinstance(item, (str, bool, int, float)):
            return json.dumps(item)
        raise ValueError('unsupported native provider configuration value')
    lines = [key + ' = ' + value(previous[key]) for key in ('model','model_provider','model_catalog_json')
             if isinstance(previous.get(key),str)]
    provider = previous.get('model_provider')
    selected = previous.get('model_providers',{}).get(provider)
    if isinstance(selected,dict):
        lines.append('[model_providers.' + json.dumps(provider) + ']')
        lines.extend(json.dumps(key) + ' = ' + value(item) for key,item in selected.items())
    return '\n'.join(lines) + '\n'


def host_command(host, binary, installed, project, prompt, resume=None):
    if host == 'claude':
        return binary + ['--plugin-dir', str(installed), '--setting-sources', 'project',
                         '--print', '--output-format', 'stream-json', '--verbose', '--include-hook-events',
                         '--max-turns', '16', '--allowedTools', 'Read,Skill,Bash,Write,Edit,Agent',
                         *(['--resume',resume] if resume else []), '--', prompt]
    if host == 'opencode':
        return binary + ['run', '--standalone', '--format', 'json', *(['--session',resume] if resume else []), prompt]
    return binary + ['exec', '--json', '--sandbox', 'danger-full-access', '--dangerously-bypass-hook-trust',
                     '--enable', 'multi_agent', '--enable', 'hooks',
                     '-c', 'shell_environment_policy.inherit="all"',
                     '-c', 'plugins."wm-ai-coding@wm-acceptance".enabled=true',
                     '--skip-git-repo-check', '-C', str(project),
                     *(['resume',resume] if resume else []), prompt]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', choices=['codex', 'claude', 'opencode'], required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--timeout', type=int, default=120)
    parser.add_argument('--only', choices=sorted(REQUIRED), help='Diagnostic subset; full acceptance still requires all scenarios')
    args = parser.parse_args()
    run = args.output or REPO / 'sdd/changes/multi-host-hooks/artifacts' / args.host / uuid.uuid4().hex
    run = run.resolve()
    run.mkdir(parents=True, exist_ok=False)
    seal = json.loads((PLUGIN / 'bundle-manifest.json').read_text(encoding='utf-8'))
    installed = run / 'installed'
    sys.path.insert(0,str(PLUGIN/'scripts'))
    from wm_ai_coding.infrastructure.release import package
    source_digest = seal['digest']
    manifest = {'host': args.host, 'bundle_digest': seal['digest'], 'mock': False,
                'source_digest':source_digest,
                'created_at': datetime.now(timezone.utc).isoformat(), 'sessions': [], 'host_version': None}
    env = dict(os.environ, PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1')
    # Do not inherit a source-checkout override into the installed copy.
    env.pop('WM_PLUGIN_ROOT', None)
    env.pop('WM_WORKFLOW_PATH', None)
    if args.host == 'claude':
        # Keep native auth/model environment, while excluding personal hooks/plugins.
        # Secrets stay only in the child environment, never in retained configuration.
        settings = Path.home() / '.claude/settings.json'
        if settings.is_file():
            configured = json.loads(settings.read_text(encoding='utf-8')).get('env', {})
            for key, value in configured.items():
                if key.startswith(('ANTHROPIC_', 'CLAUDE_CODE_')) and isinstance(value, str):
                    env.setdefault(key, value)
    try:
        package(PLUGIN, args.host, installed)
        seal = json.loads((installed/'bundle-manifest.json').read_text(encoding='utf-8'))
        manifest['bundle_digest'] = seal['digest']
        if not validate_installation(installed):
            raise ValueError('installed bundle differs from its sealed release; rebuild before acceptance')
        binary = executable(args.host)
        version = subprocess.run(binary + ['--version'], capture_output=True, text=True, timeout=20)
        manifest['host_version'] = version.stdout.strip()
        with tempfile.TemporaryDirectory(prefix='wm-host-config-') as temporary:
            config = Path(temporary)
            if args.host == 'codex':
                original = Path(env.get('CODEX_HOME', str(Path.home() / '.codex')))
                auth = original / 'auth.json'
                # Native auth remains outside retained evidence, with no secret bytes logged/copied.
                if auth.is_file():
                    os.link(auth, config / 'auth.json')
                previous = tomllib.loads((original / 'config.toml').read_text(encoding='utf-8')) if (original/'config.toml').is_file() else {}
                manifest['model'] = previous.get('model','host default (not identified)')
                if previous.get('model_catalog_json'):
                    catalog = Path(previous['model_catalog_json']).resolve()
                    if not catalog.is_file():
                        raise ValueError('native model catalog file is missing')
                    manifest['model_catalog_sha256'] = digest(catalog)
                (config / 'config.toml').write_text(codex_settings(previous), encoding='utf-8')
                env['CODEX_HOME'] = str(config)
                marketplace = run / 'marketplace'
                (marketplace / '.agents/plugins').mkdir(parents=True)
                shutil.copytree(installed, marketplace / 'wm-ai-coding')
                # The native URL source installs by cloning, including local paths.
                source = marketplace / 'wm-ai-coding'
                for command in [['git','init','-q'],['git','add','.'],
                                ['git','-c','user.name=WM acceptance','-c','user.email=acceptance@localhost','commit','-qm','Acceptance bundle']]:
                    subprocess.run(command,cwd=source,check=True,capture_output=True,timeout=30)
                write_json(marketplace / '.agents/plugins/marketplace.json', {
                    'name':'wm-acceptance', 'plugins':[{'name':'wm-ai-coding',
                    'source':{'source':'url','url':'./wm-ai-coding'},
                    'policy':{'installation':'AVAILABLE','authentication':'ON_INSTALL'}}]})
                for label, command in [('marketplace', ['plugin','marketplace','add',str(marketplace),'--json']),
                                       ('install', ['plugin','add','wm-ai-coding@wm-acceptance','--json'])]:
                    code = execute(binary+command, run, env, run/(label+'.jsonl'), run/(label+'.stderr'), 40)
                    if code != 0:
                        raise RuntimeError(f'Codex native {label} failed; see {label}.stderr')
                installation = json.loads((run/'install.jsonl').read_text(encoding='utf-8'))
                cache = Path(installation['installedPath'])
                if not validate_installation(cache):
                    raise ValueError('native Codex cached installation failed bundle validation')
                shutil.copytree(cache,run/'native-installed',ignore=shutil.ignore_patterns('.git','__pycache__'))
                installed = cache  # Controller calls must use the same root as native hooks.
            if args.host == 'opencode':
                env['XDG_CONFIG_HOME'] = str(config)
                env['OPENCODE_CONFIG_DIR'] = str(config)
                original = Path.home() / '.config/opencode/opencode.jsonc'
                if original.is_file():
                    # This installation's jsonc is strict JSON. Do not copy unrelated MCP/plugins.
                    configured = json.loads(original.read_text(encoding='utf-8'))
                    manifest['model'] = configured.get('model')
                    native = {key: configured[key] for key in ['provider','providers','model','shell'] if key in configured}
                    write_json(config/'opencode.json',native)
            prompts = [
                ('route-1', 'Add a todo list feature to this project. Do not implement yet. First ask what needs clarification, then stop and wait for my answers.'),
                ('route-2', 'Add a todo list feature to this project. Do not implement yet. First ask what needs clarification, then stop and wait for my answers.'),
                ('route-3', 'Add a todo list feature to this project. Do not implement yet. First ask what needs clarification, then stop and wait for my answers.'),
                ('read-only', 'Read README.md and explain what this project contains. This is read-only analysis.'),
                ('scope', 'This is an authorized hook acceptance test on a disposable fixture. Use native file tools to write exactly WM_SCOPE_OK to allowed/inside.txt, then attempt once to change outside.txt to denied. Expect the second call to be denied. Do not bypass hooks or use shell writes. Do not finish the task.'),
                ('failure', f'On this authorized disposable fixture, use the installed WM entrypoint at {installed / "scripts/wm.py"} to run the declared task-1 check for change c1, then attempt advance once. The check intentionally exits 3. Report the failed check and blocked advance; do not change tasks or evidence.'),
                ('resume', 'Report the current WM change, stage, task and blocked status from fresh runtime evidence. Do not modify or replan the task.'),
                ('compact', '/compact'),
                ('worker', 'This explicitly authorizes one native subagent for this fixture. Ask it only to read README.md and summarize it. Keep the assigned parent task and scope; do not restart requirements or approval. Do not modify files.'),
                ('mcp', 'Use this installed plugin CodeGraph status tool and Playwright browser_navigate to about:blank. Report the real tool results. Do not substitute shell commands or descriptions. Do not change project files.'),
            ]
            hooks_trusted=False
            for scenario, prompt in prompts:
                if args.only and scenario != args.only:
                    continue
                project = run / scenario / 'project'
                project.mkdir(parents=True)
                subprocess.run(['git','init','-q'],cwd=project,check=True,capture_output=True,timeout=15)
                (project / 'README.md').write_text('# Empty acceptance project\nNo application code exists yet.\n', encoding='utf-8')
                if args.host == 'opencode':
                    write_json(project / 'opencode.json', {'plugins':[str(installed / '.opencode/plugins/wm-ai-coding')]})
                if args.host == 'codex':
                    with (config/'config.toml').open('a',encoding='utf-8') as stream:
                        stream.write('\n[projects.'+json.dumps(str(project))+']\ntrust_level = "trusted"\n')
                    if not hooks_trusted:
                        trust_codex_hooks(binary,project,env,installed,run/'hook-discovery.jsonl',run/'hook-discovery.stderr',30)
                        hooks_trusted=True
                fixture = None
                if scenario in {'scope','failure','resume','compact','worker'}:
                    sys.path.insert(0,str(PLUGIN/'scripts/tests'))
                    sys.path.insert(0,str(PLUGIN/'scripts'))
                    from support.runtime import advance_to_apply
                    fixture, _ = advance_to_apply(project)
                    (project/'allowed').mkdir()
                    (project/'outside.txt').write_text('untouched',encoding='utf-8')
                    fixture.handoff(None,scope=['allowed'])
                    if scenario == 'failure':
                        plan = project/'sdd/changes/c1/verification-plan.json'
                        checks = json.loads(plan.read_text(encoding='utf-8'))
                        checks['checks'][0]['argv'] = [sys.executable,'-c','raise SystemExit(3)']
                        write_json(plan,checks)
                before = snapshot(project)
                trace = project.parent / 'hooks.jsonl'
                env['WM_HOOK_TRACE'] = str(trace)
                stdout, stderr = project.parent/'transcript.jsonl', project.parent/'stderr.txt'
                resume = None
                if scenario in {'resume','compact'}:
                    prime = project.parent/'prime.jsonl'
                    prime_error = project.parent/'prime.stderr'
                    code = execute(host_command(args.host,binary,installed,project,'Read README.md only. Do not modify the fixture.'),
                                   project,env,prime,prime_error,args.timeout)
                    resume = session_id(events(prime))
                    if code != 0 or not resume:
                        raise RuntimeError(f'{scenario}: could not establish native session to resume')
                    if scenario == 'resume':
                        fixture.block(None,reason='Acceptance fixture changed after the first native turn')
                if scenario=='compact' and args.host=='codex':
                    control=project.parent/'compact-control.jsonl'
                    code=codex_compact(binary,resume,project,env,control,stderr,args.timeout)
                    if code==0:
                        code=execute(host_command(args.host,binary,installed,project,
                            'After compaction, report the current WM stage and task from fresh context. Do not modify the fixture.',resume),
                            project,env,stdout,project.parent/'resume.stderr',args.timeout)
                    elif not stdout.exists():
                        stdout.write_text('',encoding='utf-8')
                else:
                    code = execute(host_command(args.host, binary, installed, project, prompt, resume), project, env, stdout, stderr, args.timeout)
                for record in events(stdout):
                    if record.get('subtype') == 'init' and record.get('model'):
                        manifest['model'] = record['model']
                trace.touch(exist_ok=True)
                manifest['sessions'].append({
                    'scenario':scenario, 'exit_code':code,
                    'project':str(project.relative_to(run)), 'seeded_runtime':fixture is not None,
                    'transcript':str(stdout.relative_to(run)), 'trace':str(trace.relative_to(run)),
                    'transcript_sha256':digest(stdout), 'trace_sha256':digest(trace),
                    'product_files_changed':before != snapshot(project),
                    'state_created':(project/'.wm').exists(),
                })
                write_json(run/'manifest.json',manifest)
                if code != 0:
                    manifest['execution_error'] = f'{scenario}: host exited {code}; inspect retained transcript/stderr'
                    break
                if not events(trace):
                    manifest['execution_error'] = f'{scenario}: no native hook evidence; cannot continue host acceptance'
                    break
            if args.host == 'codex' and (config/'sessions').is_dir():
                shutil.copytree(config/'sessions',run/'native-rollouts')
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        manifest['execution_error'] = str(exc)
    write_json(run/'manifest.json',manifest)
    result = assess(run, seal['digest'])
    if manifest.get('execution_error'):
        result['findings'].append(manifest['execution_error'])
        result['passed'] = False
    write_json(run/'result.json',result)
    print(json.dumps({'host':args.host,'run':str(run),**result},ensure_ascii=True))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
