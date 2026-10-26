"""Run the JS plugin with native-shaped context and the real Python bridge."""
from pathlib import Path
import subprocess
import unittest

from support.paths import PLUGIN_ROOT


class OpenCodePluginTests(unittest.TestCase):
    def test_plugin_lifecycle_and_bridge(self):
        entry = PLUGIN_ROOT / '.opencode/plugins/wm-ai-coding/index.js'
        self.assertTrue(entry.is_file(), 'OpenCode v2 directory entrypoint is missing')
        result = subprocess.run(['node', str(PLUGIN_ROOT / 'scripts/tests/support/opencode-contract.mjs'), str(entry)],
                                capture_output=True, text=True, encoding='utf-8', timeout=45)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn('OpenCode contract passed', result.stdout)
