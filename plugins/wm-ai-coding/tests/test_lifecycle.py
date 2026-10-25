"""Behavioral coverage for canonical routing and lifecycle support evidence."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from test_runtime import machine_for, write_change, advance_stage, advance_to_apply
from wm_ai_coding.machine import MachineError
from wm_ai_coding.registry import role_for


def specify(repo):
    change = write_change(repo)
    machine = machine_for(repo)
    machine.init(gitignore=False)
    advance_stage(machine)
    machine.set_frontend(None, False)
    return machine, change


def child(machine, parent, skill, output="design.md"):
    packet = machine.handoff(None, scope=parent['scope'], skill=skill, parent_id=parent['id'])
    machine.finish_handoff(None, packet['id'], 'completed', [f"sdd/changes/c1/{output}"])
    return packet


class LifecycleCompatibility(unittest.TestCase):
    def test_legacy_browser_acceptance_routes_to_testing_during_apply(self):
        with tempfile.TemporaryDirectory() as d:
            m,c=advance_to_apply(Path(d));h=m.handoff(None,scope=['sdd'])
            packet=m.handoff(None,scope=['sdd'],skill='research-with-playwright',parent_id=h['id'])
            self.assertEqual('test-execution',packet['skill'])

    def test_invalid_alias_target_is_rejected_before_loading_workflow(self):
        import yaml
        from wm_ai_coding.workflow import load_workflow,WorkflowError
        from wm_ai_coding.registry import find_registry_path
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); workflow=root/'workflow.yaml';registry=root/'registry.yaml'
            data=yaml.safe_load(machine_for(root).workflow.path.read_text(encoding='utf-8'))
            original=find_registry_path(machine_for(root).workflow.path)
            self.assertIsNotNone(original)
            roles=yaml.safe_load(original.read_text(encoding='utf-8'))
            roles['aliases']['obsolete-skill']='missing-skill'
            workflow.write_text(yaml.safe_dump(data),encoding='utf-8')
            registry.write_text(yaml.safe_dump(roles),encoding='utf-8')
            with self.assertRaisesRegex(WorkflowError,'invalid skill alias'):
                load_workflow(workflow)

    def test_old_profile_invocation_returns_canonical_identity(self):
        with tempfile.TemporaryDirectory() as d:
            m, c = advance_to_apply(Path(d))
            parent = m.handoff(None, scope=['sdd'])
            packet = m.handoff(None, scope=['sdd'], skill='python-ai-coding', parent_id=parent['id'])
            self.assertEqual('python-development', packet['skill'])
            self.assertEqual('python-ai-coding', packet['requested_skill'])
            self.assertEqual('profile', role_for(m.workflow, 'python-development', 'apply'))

    def test_old_primary_invocation_runs_the_canonical_stage(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d); write_change(repo); m = machine_for(repo); m.init(gitignore=False)
            packet = m.handoff(None, scope=['sdd'], skill='brainstorming')
            self.assertEqual('requirements-analysis', packet['skill'])
            m.finish_handoff(None, packet['id'], 'completed', ['sdd/changes/c1/design.md'])
            self.assertEqual('specify', m.advance()['changes']['c1']['stage'])

    def test_migrate_rebaselines_active_work_but_preserves_archived_history(self):
        with tempfile.TemporaryDirectory() as d:
            repo=Path(d);m,c=advance_to_apply(repo)
            state=m.store.read(); archived=json.loads(json.dumps(state['changes']['c1']))
            archived.update(status='archived', evidence_snapshot={'original':'keep'}, last_handoff={'skill':'openspec-archive-change'})
            state['changes']['historical']=archived
            state['workflow']['checksum']='legacy-checksum'
            m.store.write(state, expected_revision=state['revision'], event='test-legacy')
            migrated=m.migrate()
            self.assertEqual('tasks', migrated['changes']['c1']['stage'])
            self.assertNotIn('tasks', migrated['changes']['c1']['baselines'])
            self.assertEqual(archived, migrated['changes']['historical'])


class LifecycleSubsteps(unittest.TestCase):
    def test_review_cannot_start_before_test_execution_in_new_parent(self):
        from test_hardening import verified
        with tempfile.TemporaryDirectory() as d:
            m,c=verified(Path(d));h=m.handoff(None,scope=['sdd'])
            with self.assertRaisesRegex(MachineError,'test-execution'):
                m.handoff(None,scope=['sdd'],skill='code-review',parent_id=h['id'])

    def test_source_change_invalidates_test_execution_before_review(self):
        from test_hardening import verified
        with tempfile.TemporaryDirectory() as d:
            repo=Path(d);m,c=verified(repo);h=m.handoff(None,scope=['sdd'])
            child(m,h,'test-execution','verification.md')
            (repo/'implementation.py').write_text('changed = True\n',encoding='utf-8')
            with self.assertRaisesRegex(MachineError,'test-execution'):
                m.handoff(None,scope=['sdd'],skill='code-review',parent_id=h['id'])

    def test_frontend_and_test_design_can_extend_design_after_technical_step(self):
        with tempfile.TemporaryDirectory() as d:
            m,c=specify(Path(d));m.set_frontend(None,True);h=m.handoff(None,scope=['sdd'])
            child(m,h,'technical-design')
            f=m.handoff(None,scope=['sdd'],skill='frontend-design',parent_id=h['id'])
            with (c/'design.md').open('a',encoding='utf-8') as stream:
                stream.write('\n## Frontend design\nKeyboard-accessible example flow.\n')
            m.finish_handoff(None,f['id'],'completed',['sdd/changes/c1/design.md'])
            t=m.handoff(None,scope=['sdd'],skill='test-design',parent_id=h['id'])
            (c/'test-design.md').write_text('Verify the keyboard-accessible example flow.',encoding='utf-8')
            m.finish_handoff(None,t['id'],'completed',['sdd/changes/c1/test-design.md'])
            m.approve_design(reference='test:approved-complete-design')
            m.finish_handoff(None,h['id'],'completed',['sdd/changes/c1/design.md'])
            self.assertEqual('tasks',m.advance()['changes']['c1']['stage'])

    def test_test_design_change_invalidates_existing_design_approval(self):
        with tempfile.TemporaryDirectory() as d:
            m,c=advance_to_apply(Path(d))
            (c/'test-design.md').write_text('Changed test scope',encoding='utf-8')
            with self.assertRaisesRegex(MachineError,'design_approved'):
                m.advance()

    def test_missing_design_support_blocks_stage_return(self):
        with tempfile.TemporaryDirectory() as d:
            m,c=specify(Path(d)); h=m.handoff(None,scope=['sdd'])
            with self.assertRaisesRegex(MachineError,'required.*technical-design'):
                m.finish_handoff(None,h['id'],'completed',['sdd/changes/c1/design.md'])

    def test_test_design_cannot_run_before_technical_design(self):
        with tempfile.TemporaryDirectory() as d:
            m,c=specify(Path(d));h=m.handoff(None,scope=['sdd'])
            with self.assertRaisesRegex(MachineError,'technical-design'):
                m.handoff(None,scope=['sdd'],skill='test-design',parent_id=h['id'])

    def test_support_steps_are_bound_to_parent_and_current_planning(self):
        with tempfile.TemporaryDirectory() as d:
            m,c=specify(Path(d));h=m.handoff(None,scope=['sdd'])
            child(m,h,'technical-design');child(m,h,'test-design','test-design.md')
            (c/'proposal.md').write_text('Changed scope',encoding='utf-8')
            with self.assertRaisesRegex(MachineError,'required|stale'):
                m.finish_handoff(None,h['id'],'completed',['sdd/changes/c1/design.md'])

    def test_complete_design_can_return_then_advance(self):
        with tempfile.TemporaryDirectory() as d:
            m,c=specify(Path(d));h=m.handoff(None,scope=['sdd'])
            child(m,h,'technical-design');child(m,h,'test-design','test-design.md')
            m.approve_design(reference='test:user-approved')
            m.finish_handoff(None,h['id'],'completed',['sdd/changes/c1/design.md'])
            self.assertEqual('tasks', m.advance()['changes']['c1']['stage'])

    def test_previous_parent_support_cannot_complete_new_parent(self):
        with tempfile.TemporaryDirectory() as d:
            m,c=specify(Path(d));h=m.handoff(None,scope=['sdd'])
            child(m,h,'technical-design');child(m,h,'test-design','test-design.md')
            m.finish_handoff(None,h['id'],'completed',['sdd/changes/c1/design.md'])
            h=m.handoff(None,scope=['sdd'])
            with self.assertRaisesRegex(MachineError,'technical-design'):
                m.finish_handoff(None,h['id'],'completed',['sdd/changes/c1/design.md'])

    def test_frontend_design_is_completed_between_technical_and_test_design(self):
        with tempfile.TemporaryDirectory() as d:
            m,c=specify(Path(d));m.set_frontend(None,True);h=m.handoff(None,scope=['sdd'])
            child(m,h,'technical-design')
            with self.assertRaisesRegex(MachineError,'frontend'):
                m.handoff(None,scope=['sdd'],skill='test-design',parent_id=h['id'])

    def test_operation_cannot_replace_primary_stage_acceptance(self):
        with tempfile.TemporaryDirectory() as d:
            repo=Path(d);write_change(repo);m=machine_for(repo);m.init(gitignore=False)
            h=m.handoff(None,scope=['sdd'],skill='change-initialization')
            m.finish_handoff(None,h['id'],'completed',['sdd/changes/c1/design.md'])
            with self.assertRaisesRegex(MachineError,'primary|matching'):
                m.advance()


class ArchiveArtifactRelocation(unittest.TestCase):
    def test_archive_preserves_acceptance_with_change_local_declared_artifact(self):
        from test_hardening import verified
        from test_runtime import complete_supports
        from wm_ai_coding.reviews import record_review
        from wm_ai_coding.archives import verify_archive
        with tempfile.TemporaryDirectory() as d:
            repo=Path(d);m,c=verified(repo)
            plan=json.loads((c/'verification-plan.json').read_text(encoding='utf-8'))
            plan['checks'][0]['artifacts']=['sdd/changes/c1/test-design.md']
            (c/'verification-plan.json').write_text(json.dumps(plan),encoding='utf-8')
            h=m.handoff(None,scope=['sdd']);record=m.run_check(None,'suite')
            record_review(repo,c,reviewer='fixture self review',mode='self',findings=[])
            (c/'verification.json').write_text(json.dumps({'schema_version':1,'status':'passed','coverage':{
                'capability::R1':[record['id']],'capability::R1::success':[record['id']]}}),encoding='utf-8')
            complete_supports(m,h)
            m.finish_handoff(None,h['id'],'completed',['sdd/changes/c1/verification.md']);m.advance()
            m.sync_specs();advance_stage(m);m.handoff(None,scope=['sdd'])
            state=m.archive(None)
            archived=repo/state['changes']['c1']['archive_path']
            self.assertFalse(c.exists())
            self.assertTrue((archived/'test-design.md').is_file())
            self.assertTrue(verify_archive(archived)['valid'])
            self.assertEqual('archived',m.archive('c1')['changes']['c1']['status'])
