"""Startup context must route work without caching live workflow state."""
import tempfile
import unittest
from pathlib import Path

from wm_ai_coding.integrations.hook_bridge import dispatch
from support.runtime import advance_to_apply


class BootstrapTests(unittest.TestCase):
    def test_nested_git_project_does_not_inherit_parent_workflow(self):
        with tempfile.TemporaryDirectory() as directory:
            advance_to_apply(Path(directory))
            nested = Path(directory) / 'other'
            (nested / '.git').mkdir(parents=True)
            text = dispatch('claude', 'SessionStart', {'cwd':str(nested)})['hookSpecificOutput']['additionalContext']
            self.assertNotIn('"change": "c1"', text)

    def test_fresh_session_contains_contract_and_host_mapping(self):
        with tempfile.TemporaryDirectory() as directory:
            result = dispatch('claude', 'SessionStart', {'cwd': directory})
            text = result['hookSpecificOutput']['additionalContext']
            self.assertIn('WM_BOOTSTRAP', text)
            self.assertIn('read-only', text)
            self.assertIn('Skill', text)
            self.assertIn('handoff', text)
            self.assertFalse((Path(directory) / '.wm').exists())

    def test_explicit_child_gets_worker_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            text = dispatch('claude', 'SessionStart', {
                'cwd': directory, 'parent_session_id': 'parent',
            })['hookSpecificOutput']['additionalContext']
            self.assertIn('WM_WORKER', text)
            self.assertNotIn('WM_BOOTSTRAP', text)
            self.assertIn('parent', text)

    def test_worker_receives_current_handoff_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            machine, _ = advance_to_apply(Path(directory))
            handoff=machine.handoff(None,scope=['allowed-worker'])
            for host in ['claude','codex']:
                text=dispatch(host,'SubagentStart',{'cwd':directory,'session_id':'parent','agent_id':'child'})['hookSpecificOutput']['additionalContext']
                self.assertIn('allowed-worker',text)
                self.assertIn(handoff['id'],text)

    def test_prompt_refreshes_brief_without_repeating_static_protocol(self):
        with tempfile.TemporaryDirectory() as directory:
            machine, _ = advance_to_apply(Path(directory))
            first = dispatch('codex', 'SessionStart', {'cwd': directory})
            prompt = dispatch('codex', 'UserPromptSubmit', {'cwd': directory})
            self.assertIn('WM_BOOTSTRAP', first['hookSpecificOutput']['additionalContext'])
            self.assertNotIn('WM_BOOTSTRAP', prompt['hookSpecificOutput']['additionalContext'])
            self.assertIn('apply', prompt['hookSpecificOutput']['additionalContext'])
            machine.block('c1', reason='new state')
            updated = dispatch('codex', 'UserPromptSubmit', {'cwd': directory})
            self.assertIn('blocked', updated['hookSpecificOutput']['additionalContext'])

    def test_unknown_host_and_event_rejected_even_without_state(self):
        with tempfile.TemporaryDirectory() as directory:
            for host, event in [('invented', 'SessionStart'), ('claude', 'Invented')]:
                with self.subTest(host=host, event=event), self.assertRaises(ValueError):
                    dispatch(host, event, {'cwd': directory})
