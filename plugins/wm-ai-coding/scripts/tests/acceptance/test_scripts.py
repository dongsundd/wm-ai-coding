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
from unittest.mock import patch

from support.paths import PLUGIN_ROOT
ENTRY = PLUGIN_ROOT / 'scripts/wm.py'


class EntryTests(unittest.TestCase):
    def invoke(self, *args):
        with tempfile.TemporaryDirectory() as cwd:
            return subprocess.run([sys.executable, '-X', 'utf8', str(ENTRY), *args], cwd=cwd, capture_output=True, text=True, encoding='utf-8')

    def test_help_lists_all_public_commands(self):
        result = self.invoke('--help')
        self.assertEqual(0, result.returncode, result.stderr)
        for name in ('status', 'hook', 'mcp', 'release', 'preflight'):
            self.assertIn(name, result.stdout)

    def test_tool_help(self):
        for name in ('hook', 'mcp', 'release', 'preflight'):
            with self.subTest(command=name):
                result = self.invoke(name, '--help')
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertIn('usage:', result.stdout)

    def test_external_cwd_and_workflow_assets(self):
        result = self.invoke('workflow', 'show')
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn('states', json.loads(result.stdout))

    def test_empty_and_unknown_commands_fail(self):
        for args in ((), ('unknown-command',)):
            result = self.invoke(*args)
            self.assertEqual(2, result.returncode)
            self.assertEqual('', result.stdout)

    def test_source_init_and_status(self):
        with tempfile.TemporaryDirectory() as repo:
            result = self.invoke('--repo', repo, 'init', '--no-gitignore')
            self.assertEqual(0, result.returncode, result.stderr)
            result = self.invoke('--repo', repo, 'status', '--json')
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn('changes', json.loads(result.stdout))

    def test_hook_json_without_state(self):
        with tempfile.TemporaryDirectory() as cwd:
            result = subprocess.run([sys.executable, str(ENTRY), 'hook', 'codex', 'SessionStart'], input=json.dumps({'cwd': cwd}), capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIsInstance(json.loads(result.stdout), dict)


