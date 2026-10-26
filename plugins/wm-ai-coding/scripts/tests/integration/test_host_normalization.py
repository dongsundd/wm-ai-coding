"""Host tool spellings must not bypass scope checks."""
from pathlib import Path
import tempfile
import unittest

from support.runtime import advance_to_apply
from wm_ai_coding.integrations.hooks import handle_hook
from wm_ai_coding.integrations.hook_bridge import failure


class NormalizationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.machine, _ = advance_to_apply(self.root)
        self.machine.handoff(None, scope=['allowed'])

    def result(self, tool, args, host='opencode'):
        payload = {'tool_name': tool, 'tool_input': args, 'cwd': str(self.root)}
        output = handle_hook(self.machine, host, 'PreToolUse', payload)
        if host == 'opencode':
            return output.get('allowed')
        return output.get('hookSpecificOutput', {}).get('permissionDecision') != 'deny'

    def test_opencode_patch_checks_all_targets_and_move_destination(self):
        safe = '*** Begin Patch\n*** Update File: allowed/a.py\n@@\n-a\n+b\n*** End Patch'
        moved = safe.replace('@@', '*** Move to: outside.py\n@@')
        extra = safe.replace('*** End Patch', '*** Add File: outside.py\n+x\n*** End Patch')
        self.assertTrue(self.result('patch', {'patchText': safe}))
        for patch in [moved, extra, '', 'not a patch', '*** Begin Patch\n*** Update File: allowed/a\nINVALID\n*** End Patch']:
            with self.subTest(patch=patch):
                self.assertFalse(self.result('patch', {'patchText': patch}))

    def test_filePath_and_move_endpoints_are_normalized(self):
        for tool, args in [
            ('write', {'filePath': 'allowed/a'}),
            ('edit', {'filePath': 'allowed/a'}),
            ('delete', {'path': 'allowed/a'}),
        ]:
            with self.subTest(tool=tool):
                self.assertTrue(self.result(tool, args))
        self.assertFalse(self.result('move', {'source': 'allowed/a', 'destination': 'outside'}))

    def test_shell_is_checked_instead_of_silently_ignored(self):
        self.assertFalse(self.result('shell', {'command': 'echo bypass > outside'}))
        self.assertFalse(self.result('bash', {'command': 'rm outside'}))
        self.assertFalse(self.result('shell', {'command': ['invalid']}))
        self.assertFalse(self.result('shell', {'command': 'wm status & echo bypass'}))

    def test_codex_can_read_files_without_declaring_a_test_but_cannot_chain_writes(self):
        for command in ["Get-Content 'allowed/a.py'",'Get-ChildItem -Name','rg --files']:
            self.assertEqual({},handle_hook(self.machine,'codex','PreToolUse',{
                'tool_name':'Bash','tool_input':{'command':command}}))
        for command in ['Get-Content a; Set-Content outside changed','rg --pre=malicious query .',
                        'Get-Content (Write-Output outside)']:
            self.assertFalse(self.result('shell',{'command':command}))

    def test_declared_command_cannot_change_its_execution_directory(self):
        import json
        import sys
        path=self.root/'sdd/changes/c1/verification-plan.json'
        checks=json.loads(path.read_text(encoding='utf-8'))
        checks['checks'][0]['argv']=['python','-V']
        path.write_text(json.dumps(checks),encoding='utf-8')
        self.assertTrue(self.result('shell',{'command':'python -V','workdir':str(self.root)}))
        self.assertFalse(self.result('shell',{'command':'python -V','workdir':str(self.root.parent)}))

    def test_relative_targets_resolve_against_actual_workdir(self):
        payload = {'tool_name': 'write', 'tool_input': {'filePath': 'outside'}, 'cwd': str(self.root.parent)}
        self.assertFalse(handle_hook(self.machine, 'opencode', 'PreToolUse', payload)['allowed'])

    def test_unknown_tools_and_malformed_inputs_do_not_allow_writes(self):
        for tool, args in [('custom_mutate', {}), ('patch', []), ('Write', {'file_path': 42})]:
            with self.subTest(tool=tool):
                self.assertFalse(self.result(tool, args))
        self.assertEqual({}, handle_hook(self.machine, 'opencode', 'PreToolUse', {'tool_name': 'read', 'tool_input': {'filePath': 'outside'}}))
        self.assertFalse(failure('opencode', 'PreToolUse', RuntimeError('bridge failed'))['allowed'])

    def test_codex_freeform_patch_and_claude_original_payload_still_work(self):
        patch = '*** Begin Patch\n*** Add File: allowed/a\n+x\n*** End Patch'
        self.assertTrue(self.result('apply_patch', patch, 'codex'))
        self.assertTrue(self.result('Write', {'file_path': 'allowed/a'}, 'claude'))
        self.assertFalse(self.result('Write', {'file_path': '../outside'}, 'claude'))

    def test_known_mcp_observations_defer_to_host_but_unknown_tool_is_denied(self):
        for tool in ['mcp__plugin_wm_codegraph__status','wm_playwright_browser_navigate']:
            self.assertEqual({}, handle_hook(self.machine,'opencode','PreToolUse',{'tool_name':tool,'tool_input':{}}))
        self.assertFalse(self.result('mcp__unknown__mutate',{}))

    def test_codex_namespaced_collaboration_controls_are_not_mistaken_for_writes(self):
        for tool in ['collaborationspawn_agent','collaborationwait','collaborationwait_agent','collaborationlist_agents','collaborationsend_input','collaborationclose_agent']:
            self.assertEqual({},handle_hook(self.machine,'codex','PreToolUse',{'tool_name':tool,'tool_input':{}}))
        self.assertFalse(self.result('collaborationwrite_file',{}))
