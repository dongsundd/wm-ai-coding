"""Acceptance for the public CLI and its internal dependency boundaries."""
import ast
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from support.paths import PLUGIN_ROOT
ENTRY = PLUGIN_ROOT / 'scripts/wm.py'


class StructureTests(unittest.TestCase):
    def test_hook_accepts_only_exact_unified_source_entry(self):
        from wm_ai_coding.integrations import hooks
        with tempfile.TemporaryDirectory() as directory:
            machine = Mock()
            machine.repo = Path(directory)
            machine.status.return_value = {'active_change': 'c1', 'changes': {'c1': {'stage': 'apply'}}}
            machine._change_path.return_value = machine.repo / 'sdd/changes/c1'
            with patch.object(hooks, 'load_plan', return_value=[]):
                for path, expected in [(PLUGIN_ROOT / 'scripts/wm.py', 'allow'), (machine.repo / 'wm.py', 'deny')]:
                    response = hooks.handle_hook(machine, 'codex', 'PreToolUse', {'tool_name': 'Bash', 'tool_input': {'command': f'python "{path.as_posix()}" status'}})
                    self.assertEqual(expected, response['hookSpecificOutput']['permissionDecision'])

    def test_tests_are_nested_and_have_no_test_module_dependencies(self):
        self.assertFalse((PLUGIN_ROOT / 'tests').exists())
        tests = PLUGIN_ROOT / 'scripts/tests'
        for name in ('unit', 'integration', 'acceptance', 'support'):
            self.assertTrue((tests / name / '__init__.py').is_file())
        for path in tests.rglob('*.py'):
            for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
                if isinstance(node, ast.ImportFrom):
                    names = (node.module or '').split('.')
                    self.assertFalse(any(name.startswith('test_') for name in names), str(path))

    def test_only_public_entry_at_scripts_root(self):
        self.assertEqual({'wm.py', 'pyproject.toml'}, {p.name for p in (PLUGIN_ROOT / 'scripts').iterdir() if p.is_file()})
        package = PLUGIN_ROOT / 'scripts/wm_ai_coding'
        self.assertEqual({'__init__.py', 'entrypoint.py'}, {p.name for p in package.glob('*.py')})
        for group in ('commands', 'lifecycle', 'evidence', 'integrations', 'infrastructure'):
            self.assertTrue((package / group / '__init__.py').is_file())

    def test_services_do_not_import_commands(self):
        for group in ('lifecycle', 'evidence', 'integrations', 'infrastructure'):
            for path in (PLUGIN_ROOT / 'scripts/wm_ai_coding' / group).rglob('*.py'):
                for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
                    if isinstance(node, ast.ImportFrom):
                        self.assertNotIn('commands', (node.module or '').split('.'), str(path))

    def test_state_machine_operations_have_distinct_owners(self):
        from wm_ai_coding.lifecycle.machine import StateMachine
        self.assertTrue(StateMachine.approve_design.__module__.endswith('.planning'))
        self.assertTrue(StateMachine.handoff.__module__.endswith('.handoffs'))
        self.assertTrue(StateMachine.archive.__module__.endswith('.closure'))

    def test_runtime_hash_covers_nested_modules(self):
        from wm_ai_coding.evidence import runs
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / 'runtime'
            (package / 'evidence').mkdir(parents=True)
            (package / 'integrations').mkdir()
            nested = package / 'integrations/mcp.py'
            nested.write_text('version = 1')
            with patch.object(runs, '__file__', str(package / 'evidence/runs.py')):
                before = runs.environment_identity(Path(directory), [])['runtime_digest']
                nested.write_text('version = 2')
                after = runs.environment_identity(Path(directory), [])['runtime_digest']
        self.assertNotEqual(before, after)

    def test_mcp_preserves_streams_and_exit_code(self):
        from wm_ai_coding.integrations import mcp
        with patch.object(mcp.shutil, 'which', return_value='server-bin'), patch.object(mcp.subprocess, 'call', return_value=17) as call:
            self.assertEqual(17, mcp.launch('codegraph', ['serve', '--mcp']))
            call.assert_called_once_with(['server-bin', 'serve', '--mcp'])

    def test_preflight_output_and_exit_code(self):
        from wm_ai_coding.commands import preflight
        payload = {'ok': False, 'checks': [{'name': 'node', 'available': False, 'detail': 'missing'}], 'install_results': []}
        with patch.object(preflight, 'inspect_dependencies', return_value=payload):
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                self.assertEqual(1, preflight.main([]))
            self.assertIn('MISSING node: missing', stream.getvalue())
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                self.assertEqual(1, preflight.main(['--json']))
            self.assertEqual(payload, json.loads(stream.getvalue()))


