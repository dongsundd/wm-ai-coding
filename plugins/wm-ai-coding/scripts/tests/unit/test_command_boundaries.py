"""Behavioral and structural contracts for the public CLI boundary."""
import ast
import contextlib
import importlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from support.paths import PLUGIN_ROOT


class CommandBoundaryTests(unittest.TestCase):
    def test_every_command_owns_its_main(self):
        for name in ('hook', 'mcp', 'preflight', 'release', 'workflow'):
            with self.subTest(command=name):
                module = importlib.import_module('wm_ai_coding.commands.' + name)
                self.assertEqual(module.__name__, module.main.__module__)
                if name != 'workflow':
                    self.assertTrue(callable(module.add_arguments))
                    self.assertTrue(callable(module.run))

    def test_services_do_not_own_cli_parsing_or_process_io(self):
        package = PLUGIN_ROOT / 'scripts/wm_ai_coding'
        for group in ('integrations', 'infrastructure', 'lifecycle', 'evidence'):
            for path in (package / group).glob('*.py'):
                with self.subTest(file=path.name):
                    for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
                        if isinstance(node, ast.Import):
                            self.assertNotIn('argparse', [item.name for item in node.names])
                        if isinstance(node, ast.ImportFrom):
                            self.assertNotEqual('argparse', node.module)
                        if isinstance(node, ast.FunctionDef):
                            self.assertNotEqual('main', node.name)
                        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                            self.assertNotIn(node.func.id, {'print', 'input'})
                        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == 'sys':
                            self.assertNotIn(node.attr, {'argv', 'stdin', 'stdout', 'stderr'})

    def test_workflow_has_no_second_hook_implementation(self):
        from wm_ai_coding.commands import workflow
        tree = ast.parse(Path(workflow.__file__).read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                self.assertNotIn('hooks', (node.module or '').split('.'))
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'add_parser':
                self.assertFalse(node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == 'hook')

    def test_hook_service_returns_data_without_process_io(self):
        from wm_ai_coding.integrations import hook_bridge
        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = hook_bridge.dispatch('codex', 'SessionStart', {'cwd': directory})
        self.assertEqual('', output.getvalue())
        self.assertEqual('SessionStart', result['hookSpecificOutput']['hookEventName'])

    def test_hook_service_uses_explicit_repo(self):
        from wm_ai_coding.integrations import hook_bridge
        payload = {'cwd': '/unused/payload'}
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            with patch.object(hook_bridge, 'workflow_path'), patch.object(hook_bridge, 'load_workflow') as load, patch.object(hook_bridge, 'StateMachine') as machine, patch.object(hook_bridge, 'handle_hook', return_value={'ok': True}) as handle:
                self.assertEqual({'ok': True}, hook_bridge.dispatch('codex', 'PreToolUse', payload, repo=repo))
                machine.assert_called_once_with(repo.resolve(), load.return_value)
                handle.assert_called_once_with(machine.return_value, 'codex', 'PreToolUse', payload)

    def test_hook_command_owns_json_input_and_output(self):
        from wm_ai_coding.commands import hook
        payload = {'cwd': '/payload'}
        output = io.StringIO()
        with patch.object(hook, 'dispatch', return_value={'ok': True}) as dispatch, patch.object(sys, 'stdin', io.StringIO(json.dumps(payload))), contextlib.redirect_stdout(output):
            self.assertEqual(0, hook.main(['codex', 'SessionStart']))
        dispatch.assert_called_once_with('codex', 'SessionStart', payload, repo=None)
        self.assertEqual({'ok': True}, json.loads(output.getvalue()))

    def test_bad_hook_json_remains_fail_closed(self):
        from wm_ai_coding.commands import hook
        output = io.StringIO()
        with patch.object(sys, 'stdin', io.StringIO('{bad json')), contextlib.redirect_stdout(output):
            self.assertEqual(0, hook.main(['codex', 'PreToolUse']))
        result = json.loads(output.getvalue())
        self.assertEqual('deny', result['hookSpecificOutput']['permissionDecision'])

    def test_non_object_hook_json_remains_fail_closed(self):
        from wm_ai_coding.commands import hook
        output = io.StringIO()
        with patch.object(sys, 'stdin', io.StringIO('[]')), contextlib.redirect_stdout(output):
            self.assertEqual(0, hook.main(['codex', 'PreToolUse']))
        self.assertEqual('deny', json.loads(output.getvalue())['hookSpecificOutput']['permissionDecision'])

    def test_hook_execution_failure_preserves_dsh_protocol(self):
        from wm_ai_coding.commands import hook
        output = io.StringIO()
        with patch.object(hook, 'dispatch', side_effect=RuntimeError('failed')), patch.object(sys, 'stdin', io.StringIO('{}')), contextlib.redirect_stdout(output):
            self.assertEqual(0, hook.main(['dsh', 'pre-tool-use']))
        self.assertFalse(json.loads(output.getvalue())['allowed'])

    def test_hook_repo_prefix_reaches_same_command_adapter(self):
        from wm_ai_coding.commands import hook
        from wm_ai_coding.entrypoint import main
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as directory, patch.object(hook, 'dispatch', return_value={}) as dispatch, patch.object(sys, 'stdin', io.StringIO('{}')), contextlib.redirect_stdout(output):
            self.assertEqual(0, main(['--repo', directory, 'hook', 'codex', 'SessionStart']))
            dispatch.assert_called_once_with('codex', 'SessionStart', {}, repo=Path(directory))

    def test_mcp_arguments_and_exit_code_are_transparent(self):
        from wm_ai_coding.commands import mcp
        for forwarded in (['--help', '--', '--token', 'value'], ['--', '--help']):
            with self.subTest(arguments=forwarded):
                output = io.StringIO()
                with patch.object(mcp, 'launch', return_value=17) as launch, contextlib.redirect_stdout(output):
                    self.assertEqual(17, mcp.main(['codegraph', *forwarded]))
                launch.assert_called_once_with('codegraph', forwarded)
                self.assertEqual('', output.getvalue())

    def test_mcp_repo_prefix_does_not_reach_workflow_business_dispatch(self):
        from wm_ai_coding.commands import mcp
        from wm_ai_coding.entrypoint import main
        for tail in (['serve', '--mcp'], ['--', '--help']):
            with self.subTest(arguments=tail), patch.object(mcp, 'launch', return_value=17) as launch:
                self.assertEqual(17, main(['--repo', '.', 'mcp', 'codegraph', *tail]))
            launch.assert_called_once_with('codegraph', tail)

    def test_mcp_argument_errors_exit_two_without_launching(self):
        from wm_ai_coding.commands import mcp
        from wm_ai_coding.entrypoint import main
        for args in (['mcp'], ['mcp', 'unsupported'], ['--repo', '.', 'mcp']):
            with self.subTest(arguments=args), patch.object(mcp, 'launch') as launch, contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as result:
                    main(args)
                self.assertEqual(2, result.exception.code)
                launch.assert_not_called()

    def test_missing_mcp_executable_is_reported_only_by_command(self):
        from wm_ai_coding.commands import mcp
        output, errors = io.StringIO(), io.StringIO()
        with patch.object(mcp, 'launch', side_effect=FileNotFoundError('missing server')), contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            self.assertEqual(2, mcp.main(['codegraph']))
        self.assertEqual('', output.getvalue())
        self.assertIn('missing server', errors.getvalue())

    def test_mcp_service_raises_without_printing(self):
        from wm_ai_coding.integrations import mcp
        output, errors = io.StringIO(), io.StringIO()
        with patch.object(mcp.shutil, 'which', return_value=None), contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            with self.assertRaises(FileNotFoundError):
                mcp.launch('codegraph', [])
            with self.assertRaises(ValueError):
                mcp.launch('unsupported', [])
        self.assertEqual('', output.getvalue() + errors.getvalue())

    def test_tool_help_is_registered_with_real_arguments_with_or_without_repo(self):
        entry = PLUGIN_ROOT / 'scripts/wm.py'
        for name, expected in [('hook', 'event'), ('mcp', 'server'), ('release', 'verify'), ('preflight', '--project')]:
            with self.subTest(command=name):
                outputs = []
                for prefix in ([], ['--repo', '.']):
                    result = subprocess.run([sys.executable, str(entry), *prefix, name, '--help'], capture_output=True, text=True)
                    self.assertEqual(0, result.returncode, result.stderr)
                    self.assertIn(expected, result.stdout)
                    outputs.append(result.stdout)
                self.assertEqual(*outputs)


if __name__ == '__main__':
    unittest.main()
