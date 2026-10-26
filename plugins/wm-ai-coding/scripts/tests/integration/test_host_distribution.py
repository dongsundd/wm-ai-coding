"""Build an installed copy without deriving one host from another host manifest."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from support.paths import PLUGIN_ROOT
from wm_ai_coding.infrastructure.release import build, verify


class HostDistributionTests(unittest.TestCase):
    def test_codex_package_uses_compatibility_manifest_without_portable_shadowing(self):
        from wm_ai_coding.infrastructure import release
        self.assertTrue(hasattr(release,'package'),'host-specific package builder missing')
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'source'
            shutil.copytree(PLUGIN_ROOT,source,ignore=shutil.ignore_patterns('__pycache__','build','dist','*.egg-info'))
            build(source)
            result=release.package(source,'codex',Path(directory)/'codex')
            target=Path(result['path'])
            self.assertFalse((target/'plugin.json').exists())
            self.assertTrue((source/'plugin.json').is_file())
            self.assertTrue(verify(target)['valid'])
            self.assertEqual('./hooks/codex.json',json.loads((target/'.codex-plugin/plugin.json').read_text(encoding='utf-8'))['hooks'])
            self.assertNotEqual(result['digest'],result['source_digest'])
            with self.assertRaises(ValueError):
                release.package(source,'codex',target)

    def test_neutral_build_installed_unicode_path_and_host_specific_mcp(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / '安装 with spaces'
            shutil.copytree(PLUGIN_ROOT, root, ignore=shutil.ignore_patterns('__pycache__', 'build', 'dist', '*.egg-info'))
            # Missing generated host metadata must not prevent a fresh build.
            (root / '.codex-plugin/plugin.json').unlink()
            try:
                build(root)
            except FileNotFoundError as exc:
                self.fail(f'build still depends on generated Codex manifest: {exc}')
            self.assertTrue(verify(root)['valid'])
            codex = json.loads((root / '.codex.mcp.json').read_text(encoding='utf-8'))
            claude = json.loads((root / '.mcp.json').read_text(encoding='utf-8'))
            self.assertEqual('./', codex['mcpServers']['codegraph']['cwd'])
            self.assertEqual('scripts/wm.py', codex['mcpServers']['codegraph']['args'][0])
            self.assertIn('${CLAUDE_PLUGIN_ROOT}', claude['mcpServers']['codegraph']['args'][0])
            package = json.loads((root / '.opencode/plugins/wm-ai-coding/package.json').read_text())
            self.assertEqual('module', package['type'])
            result = subprocess.run([sys.executable, str(root / 'scripts/wm.py'), 'hook', 'claude', 'SessionStart'],
                                    input=json.dumps({'cwd': directory}), capture_output=True,
                                    text=True, encoding='utf-8', timeout=20)
            self.assertEqual(0, result.returncode, result.stderr)
            context = json.loads(result.stdout)['hookSpecificOutput']['additionalContext']
            self.assertIn(str(root.resolve()), context)
            self.assertNotIn(str(PLUGIN_ROOT), context)
            # A packaged plugin entry is part of the sealed release.
            entry = root / '.opencode/plugins/wm-ai-coding/index.js'
            entry.write_text(entry.read_text() + '\n// changed\n')
            self.assertFalse(verify(root)['valid'])
