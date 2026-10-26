"""Claude output must match each native event's consumption contract."""
from pathlib import Path
import tempfile
import unittest

from support.runtime import advance_to_apply
from wm_ai_coding.integrations.hook_bridge import dispatch
from wm_ai_coding.integrations.hooks import handle_hook


class ClaudeHooksTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.machine, _ = advance_to_apply(self.repo)
        self.machine.handoff(None, scope=['allowed'])

    def test_precompact_does_not_claim_to_inject_context(self):
        for host in ['claude','codex']:
            self.assertEqual({}, dispatch(host, 'PreCompact', {'cwd': str(self.repo)}))

    def test_compact_session_start_restores_live_state(self):
        output = dispatch('claude', 'SessionStart', {'cwd': str(self.repo), 'source': 'compact'})
        self.assertIn('WM_BOOTSTRAP', output['hookSpecificOutput']['additionalContext'])
        self.assertIn('apply', output['hookSpecificOutput']['additionalContext'])

    def test_codex_postcompact_is_observation_only_and_next_prompt_restores_state(self):
        self.assertEqual({},dispatch('codex','PostCompact',{'cwd':str(self.repo),'trigger':'manual'}))
        output=dispatch('codex','UserPromptSubmit',{'cwd':str(self.repo)})
        self.assertIn('apply',output['hookSpecificOutput']['additionalContext'])
        self.assertIn('task-1',output['hookSpecificOutput']['additionalContext'])

    def test_native_subagent_start_receives_worker_contract(self):
        output = dispatch('claude', 'SubagentStart', {
            'cwd':str(self.repo),'session_id':'parent','agent_id':'child','agent_type':'general-purpose',
        })
        self.assertIn('WM_WORKER', output['hookSpecificOutput']['additionalContext'])
        self.assertNotIn('WM_BOOTSTRAP', output['hookSpecificOutput']['additionalContext'])

    def test_post_tool_context_is_model_visible_without_replacing_result(self):
        output = handle_hook(self.machine, 'claude', 'PostToolUse', {'tool_response': {'content': 'keep'}})
        self.assertEqual('PostToolUse', output['hookSpecificOutput']['hookEventName'])
        self.assertIn('evidence', output['hookSpecificOutput']['additionalContext'])
        self.assertNotIn('updatedMCPToolOutput', output)

    def test_native_stop_and_reentrant_stop_allow_pausing(self):
        for payload in [{'last_assistant_message': 'Work remains.'}, {'stop_hook_active': True, 'completion_claim': True}]:
            self.assertEqual({}, handle_hook(self.machine, 'claude', 'Stop', payload))

    def test_in_scope_policy_does_not_auto_grant_claude_permission(self):
        output = handle_hook(self.machine, 'claude', 'PreToolUse', {
            'tool_name': 'Write', 'tool_input': {'file_path': 'allowed/a'},
        })
        self.assertNotIn('permissionDecision', output.get('hookSpecificOutput', {}))
        denied = handle_hook(self.machine, 'claude', 'PreToolUse', {
            'tool_name': 'Write', 'tool_input': {'file_path': 'outside'},
        })
        self.assertEqual('deny', denied['hookSpecificOutput']['permissionDecision'])
