"""Evidence evaluator must fail for absent, stale or merely asserted success."""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import contextlib
import io
import shutil

from support.paths import PLUGIN_ROOT


class HostAcceptanceTests(unittest.TestCase):
    def load_runner(self):
        runner = PLUGIN_ROOT / 'scripts/tests/acceptance/host_acceptance.py'
        spec = importlib.util.spec_from_file_location('host_acceptance_runner', runner)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_codex_config_keeps_only_selected_provider_and_native_model(self):
        import tomllib
        module = self.load_runner()
        previous = {'model':'fixture-model','model_provider':'custom','model_catalog_json':'D:/fixture/models.json',
                    'model_providers':{'custom':{'name':'Fixture','base_url':'https://example.invalid',
                        'wire_api':'responses','http_headers':{'X-Fixture':'temporary-only'},'requires_openai_auth':False},
                        'unrelated':{'name':'Do not copy'}},
                    'plugins':{'personal':{'enabled':True}}, 'hooks':{'personal':True}}
        actual = tomllib.loads(module.codex_settings(previous))
        self.assertEqual('fixture-model',actual['model'])
        self.assertEqual('D:/fixture/models.json',actual['model_catalog_json'])
        self.assertEqual({'custom':previous['model_providers']['custom']},actual['model_providers'])
        self.assertNotIn('hooks',actual)
        self.assertNotIn('plugins',actual)

    def test_assessment_rejects_duplicate_scenarios_and_native_provider_errors(self):
        module = self.load_runner()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'transcript.jsonl').write_text('{"type":"error","error":{"message":"provider unavailable"}}\n')
            (root/'hooks.jsonl').write_text('{"bootstrap":true}\n')
            row={'scenario':'route-1','exit_code':0,'transcript':'transcript.jsonl','trace':'hooks.jsonl',
                 'transcript_sha256':module.digest(root/'transcript.jsonl'),'trace_sha256':module.digest(root/'hooks.jsonl')}
            module.write_json(root/'manifest.json',{'bundle_digest':'current','mock':False,'host_version':'fixture','sessions':[row,row]})
            result=module.assess(root,'current')
            self.assertFalse(result['passed'])
            self.assertTrue(any('duplicate' in item for item in result['findings']))
            self.assertTrue(any('provider' in item for item in result['findings']))

    def test_mcp_requires_both_real_tool_results_not_only_invocations(self):
        module = self.load_runner()
        calls=[{'type':'assistant','message':{'content':[
            {'type':'tool_use','id':'a','name':'mcp__wm_codegraph__status','input':{}},
            {'type':'tool_use','id':'b','name':'mcp__wm_playwright__browser_navigate','input':{'url':'about:blank'}},
        ]}}, {'type':'user','message':{'content':[
            {'type':'tool_result','tool_use_id':'a','content':'ok'},
            {'type':'tool_result','tool_use_id':'b','content':'failed','is_error':True},
        ]}}]
        self.assertFalse(module.native_checks('mcp',Path('.'),calls,[]))
        calls[1]['message']['content'][1]['is_error']=False
        self.assertTrue(module.native_checks('mcp',Path('.'),calls,[]))

    def test_scope_observation_accepts_native_patch_line_ending(self):
        module=self.load_runner()
        with tempfile.TemporaryDirectory() as directory:
            project=Path(directory)
            (project/'allowed').mkdir()
            (project/'allowed/inside.txt').write_text('WM_SCOPE_OK\n')
            (project/'outside.txt').write_text('untouched')
            self.assertTrue(module.native_checks('scope',project,[],[{'permissionDecision':'deny'}]))

    def test_complete_evaluator_vectors_pass_and_missing_transcript_fails(self):
        module=self.load_runner()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            rows=[]
            for scenario in sorted(module.REQUIRED):
                folder=root/scenario
                project=folder/'project'
                project.mkdir(parents=True)
                records=[{'type':'assistant','message':{'content':[
                    {'type':'tool_use','id':'route','name':'Skill','input':{'skill':'development-workflow'}}]}}]
                hooks=[{'bootstrap':True}]
                if scenario=='scope':
                    (project/'allowed').mkdir()
                    (project/'allowed/inside.txt').write_text('WM_SCOPE_OK')
                    (project/'outside.txt').write_text('untouched')
                    hooks.append({'permissionDecision':'deny'})
                if scenario=='failure':
                    (project/'.wm/runs/failed').mkdir(parents=True)
                    module.write_json(project/'.wm/runs/failed/record.json',{'exit_code':3})
                    module.write_json(project/'.wm/state.json',{'changes':{'c1':{'stage':'apply','task_receipts':{}}}})
                if scenario=='resume':hooks.append({'state':{'stage':'apply','task':'task-1','status':'blocked'}})
                if scenario=='compact':
                    hooks.append({'event':'PostCompact'})
                    hooks.append({'event':'UserPromptSubmit','state':{'stage':'apply','task':'task-1'}})
                if scenario=='worker':
                    hooks.append({'worker':True})
                    records.append({'type':'tool_use','name':'Agent','input':{}})
                if scenario=='mcp':
                    records=[{'type':'assistant','message':{'content':[
                        {'type':'tool_use','id':'a','name':'mcp__codegraph__status','input':{}},
                        {'type':'tool_use','id':'b','name':'mcp__playwright__browser_navigate','input':{'url':'about:blank'}}]}},
                        {'type':'user','message':{'content':[
                            {'type':'tool_result','tool_use_id':'a','content':'ok'},
                            {'type':'tool_result','tool_use_id':'b','content':'ok'}]}}]
                transcript=folder/'transcript.jsonl'
                trace=folder/'hooks.jsonl'
                transcript.write_text('\n'.join(json.dumps(row) for row in records))
                trace.write_text('\n'.join(json.dumps(row) for row in hooks))
                rows.append({'scenario':scenario,'exit_code':0,'project':str(project.relative_to(root)),
                             'transcript':str(transcript.relative_to(root)),'trace':str(trace.relative_to(root)),
                             'transcript_sha256':module.digest(transcript),'trace_sha256':module.digest(trace),
                             'product_files_changed':False,'state_created':False})
            module.write_json(root/'manifest.json',{'bundle_digest':'current','mock':False,'host_version':'fixture',
                                                   'model':'fixture','sessions':rows})
            self.assertTrue(module.assess(root,'current')['passed'])
            (root/'route-1/transcript.jsonl').unlink()
            self.assertFalse(module.assess(root,'current')['passed'])

    def test_real_hook_writes_opt_in_trace_without_payload_secrets(self):
        with tempfile.TemporaryDirectory() as directory:
            trace = Path(directory) / 'events.jsonl'
            env = dict(os.environ, WM_HOOK_TRACE=str(trace), PYTHONUTF8='1')
            result = subprocess.run([sys.executable, str(PLUGIN_ROOT/'scripts/wm.py'), 'hook', 'claude', 'SessionStart'],
                                    input=json.dumps({'cwd':directory,'secret':'never-log-this'}),
                                    capture_output=True,text=True,encoding='utf-8',env=env,timeout=20)
            self.assertEqual(0,result.returncode,result.stderr)
            self.assertTrue(trace.is_file(), 'native hook execution trace missing')
            text=trace.read_text(encoding='utf-8')
            self.assertNotIn('never-log-this',text)
            self.assertTrue(json.loads(text)['bootstrap'])

    def test_missing_or_claimed_only_evidence_is_rejected(self):
        runner = PLUGIN_ROOT / 'scripts/tests/acceptance/host_acceptance.py'
        self.assertTrue(runner.is_file(), 'real-host acceptance runner is missing')
        spec = importlib.util.spec_from_file_location('host_acceptance_runner', runner)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = module.assess(root, 'current')
            self.assertFalse(result['passed'])
            (root / 'result.json').write_text('{"passed":true}')
            self.assertFalse(module.assess(root, 'current')['passed'])

    def test_wrong_digest_mock_and_zero_sessions_are_not_accepted(self):
        runner = PLUGIN_ROOT / 'scripts/tests/acceptance/host_acceptance.py'
        self.assertTrue(runner.is_file(), 'real-host acceptance runner is missing')
        spec = importlib.util.spec_from_file_location('host_acceptance_runner', runner)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'manifest.json').write_text('{"bundle_digest":"stale","sessions":[],"mock":true}')
            result = module.assess(root, 'current')
            self.assertFalse(result['passed'])
            self.assertTrue(any('digest' in finding for finding in result['findings']))

    def test_runner_requires_sealed_installed_content(self):
        module=self.load_runner()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'bundle-manifest.json').write_text('{"digest":"claimed"}')
            self.assertTrue(hasattr(module,'validate_installation'),'installed content validation missing')
            self.assertFalse(module.validate_installation(root))

    def test_native_session_without_hook_evidence_stops_the_suite(self):
        module=self.load_runner()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            stub=root/'host.py'
            stub.write_text('import json\nprint(json.dumps({"type":"result","result":"no hook"}))\n')
            source=root/'source'
            shutil.copytree(PLUGIN_ROOT,source,ignore=shutil.ignore_patterns('__pycache__','build','dist','*.egg-info'))
            from wm_ai_coding.infrastructure.release import build
            build(source)
            output=root/'run'
            with patch.object(sys,'argv',['host_acceptance.py','--host','claude','--output',str(output)]), \
                 patch.object(module,'executable',return_value=[sys.executable,str(stub)]), \
                 patch.object(module,'PLUGIN',source), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(1,module.main())
            manifest=json.loads((output/'manifest.json').read_text(encoding='utf-8'))
            self.assertEqual(1,len(manifest['sessions']))
            self.assertIn('hook',manifest['execution_error'])

    def test_codex_compaction_driver_uses_native_control_requests(self):
        module=self.load_runner()
        self.assertTrue(hasattr(module,'codex_compact'),'native Codex compaction driver missing')
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            stub=root/'server.py'
            stub.write_text('''import sys,json
for line in sys.stdin:
    request=json.loads(line)
    if "id" in request:
        print(json.dumps({"id":request["id"],"result":{"method":request["method"]}}),flush=True)
    if request["method"]=="thread/compact/start":
        print(json.dumps({"method":"item/completed","params":{"item":{"type":"contextCompaction"}}}),flush=True)
        print(json.dumps({"method":"hook/completed","params":{"run":{"eventName":"postCompact","status":"completed"}}}),flush=True)
''')
            self.assertEqual(0,module.codex_compact([sys.executable,str(stub)],'thread',root,dict(os.environ),root/'out.jsonl',root/'err.txt',10))
            messages=module.events(root/'out.jsonl')
            self.assertTrue(any(row.get('result',{}).get('method')=='thread/compact/start' for row in messages))

    def test_compact_requires_fresh_context_after_the_native_event(self):
        module=self.load_runner()
        self.assertFalse(module.native_checks('compact',Path('.'),[],[{'event':'PostCompact'}]))

    def test_codex_collab_and_mcp_wire_results_are_interpreted(self):
        module=self.load_runner()
        records=[{'type':'item.completed','item':{'type':'collab_tool_call','tool':'spawn_agent','status':'completed'}}]
        self.assertTrue(module.native_checks('worker',Path('.'),records,[{'worker':True}]))
        self.assertTrue(module.native_checks('worker',Path('.'),[],[
            {'event':'PostToolUse','tool':'collaborationspawn_agent'}, {'event':'SubagentStart','worker':True}]))
        records=[{'type':'item.completed','item':{'type':'mcp_tool_call','server':server,
                    'tool':'status' if server=='codegraph' else 'browser_navigate','arguments':{'url':'about:blank'},
                    'status':'completed','result':{'isError':server=='playwright','content':[]}}} for server in ['codegraph','playwright']]
        self.assertFalse(module.native_checks('mcp',Path('.'),records,[]))

    def test_codex_hook_trust_is_scoped_to_vetted_native_package(self):
        module=self.load_runner()
        self.assertTrue(hasattr(module,'trust_codex_hooks'),'isolated native hook trust adapter missing')
        with tempfile.TemporaryDirectory(prefix='wm-host-config-') as directory:
            root=Path(directory)
            (root/'config.toml').write_text('')
            installed=root/'installed';installed.mkdir()
            command=f'python "{installed.as_posix()}/scripts/wm.py" hook codex SessionStart'
            hook={'key':'wm-ai-coding@wm-acceptance:session-start','pluginId':'wm-ai-coding@wm-acceptance',
                  'command':command,'currentHash':'sha256:'+'a'*64+'/sha256:'+'b'*64}
            stub=root/'server.py'
            stub.write_text('import sys,json\nhook='+repr(hook)+'''\nfor line in sys.stdin:
    r=json.loads(line)
    if "id" in r:
        value={"data":[{"hooks":[hook]}]} if r["method"]=="hooks/list" else {}
        print(json.dumps({"id":r["id"],"result":value}),flush=True)
''')
            env=dict(os.environ,CODEX_HOME=str(root))
            module.trust_codex_hooks([sys.executable,str(stub)],root,env,installed,root/'out',root/'err',10)
            settings=(root/'config.toml').read_text()
            self.assertIn('trusted_content_hash',settings)
            self.assertIn('sha256:'+'a'*64,settings)
