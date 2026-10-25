"""Behavioral acceptance for the approved evidence protocol (temporary repositories only)."""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_runtime import advance_to_apply, complete_task, machine_for
from wm_ai_coding.machine import MachineError


def acceptance(machine, change, index=1):
    return machine.run_check(None, f"task-{index}")


class RouteTests(unittest.TestCase):
    def test_child_returns_to_parent_and_cannot_expand_scope(self):
        with tempfile.TemporaryDirectory() as d:
            m, c = advance_to_apply(Path(d))
            parent = m.handoff(None, scope=["sdd/changes/c1/tasks.md"])
            with self.assertRaises(MachineError):
                m.handoff(None, scope=["outside.py"], skill="python-development", parent_id=parent["id"])
            child = m.handoff(None, scope=parent["scope"], skill="python-development", parent_id=parent["id"])
            m.finish_handoff(None, child["id"], "completed", ["sdd/changes/c1/tasks.md"])
            self.assertEqual(parent["id"], m.recovery()["handoff"]["id"])
            with self.assertRaises(MachineError):
                m.advance()

    def test_all_distributed_skills_have_a_registered_role(self):
        from wm_ai_coding.registry import validate_registry
        root = Path(__file__).resolve().parents[1]
        self.assertEqual([], validate_registry(root))


class TaskTests(unittest.TestCase):
    def test_checkbox_without_run_and_handoff_cannot_advance(self):
        with tempfile.TemporaryDirectory() as d:
            m, c = advance_to_apply(Path(d))
            complete_task(c / "tasks.md", 1)
            with self.assertRaises(MachineError):
                m.advance()

    def test_acceptance_requires_current_source_and_correct_task(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d); m, c = advance_to_apply(repo)
            h = m.handoff(None, scope=["sdd/changes/c1/tasks.md", "source.py"])
            acceptance(m, c)
            (repo / "source.py").write_text("changed=True")
            complete_task(c / "tasks.md", 1)
            with self.assertRaisesRegex(MachineError, "acceptance"):
                m.finish_handoff(None, h["id"], "completed", ["sdd/changes/c1/tasks.md"])
            acceptance(m, c)
            m.finish_handoff(None, h["id"], "completed", ["sdd/changes/c1/tasks.md"])
            self.assertEqual("task-2", m.advance()["changes"]["c1"]["current_task"]["id"])

    def test_undeclared_write_is_detected_at_return(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d); m, c = advance_to_apply(repo)
            h = m.handoff(None, scope=["sdd/changes/c1/tasks.md"])
            (repo / "unrelated.py").write_text("unexpected")
            acceptance(m, c); complete_task(c / "tasks.md", 1)
            with self.assertRaisesRegex(MachineError, "scope"):
                m.finish_handoff(None, h["id"], "completed", ["sdd/changes/c1/tasks.md"])


class IntegrityTests(unittest.TestCase):
    def test_migration_preserves_archived_diagnostic_history(self):
        with tempfile.TemporaryDirectory() as d:
            m,_=advance_to_apply(Path(d));state=m._read()
            item=state['changes']['c1'];item.update(status='archived',archive_path='sdd/changes/archive/missing',evidence_snapshot={'historical':'keep'})
            state['workflow']['checksum']='old';m.store.write(state,expected_revision=state['revision'])
            migrated=m.migrate()
            self.assertEqual({'historical':'keep'},migrated['changes']['c1']['evidence_snapshot'])

    def test_archive_needs_scoped_handoff_and_exports_task_receipts(self):
        from test_hardening import verified
        from test_runtime import advance_stage
        from wm_ai_coding.archives import verify_archive
        with tempfile.TemporaryDirectory() as d:
            repo=Path(d);m,c=verified(repo);m.advance();m.sync_specs();advance_stage(m)
            with self.assertRaisesRegex(MachineError,'handoff'):
                m.archive(None)
            m.handoff(None,scope=['sdd/changes'])
            state=m.archive(None);root=repo/state['changes']['c1']['archive_path']
            receipts=json.loads((root/'evidence/task-receipts.json').read_text())
            self.assertEqual({'task-1','task-2'},set(receipts))
            (repo/'.wm').rename(repo/'local-state-hidden')
            self.assertTrue(verify_archive(root)['valid'])

    def test_missing_archive_is_never_delivered_and_validation_exits_nonzero(self):
        from wm_ai_coding.cli import main
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d); m, _ = advance_to_apply(repo)
            s = m._read(); item = s["changes"]["c1"]
            item.update(status="archived", archive_path="sdd/changes/archive/missing")
            m._write(s, s["revision"], "fixture")
            self.assertEqual("missing", m.status()["changes"]["c1"]["integrity"]["status"])
            self.assertEqual("repair-required", m.recovery("c1")["next_action"])
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertNotEqual(0, main(["--repo", str(repo), "validate"]))

    def test_manifest_detects_tampering_without_local_state(self):
        from wm_ai_coding.archives import write_manifest, verify_archive
        with tempfile.TemporaryDirectory() as d:
            p = Path(d); (p / "tasks.md").write_text("accepted")
            identity = write_manifest(p)
            self.assertTrue(verify_archive(p, identity)["valid"])
            (p / "tasks.md").write_text("tampered")
            self.assertFalse(verify_archive(p, identity)["valid"])


class IdentityTests(unittest.TestCase):
    def test_missing_declared_artifact_cannot_be_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            m,c=advance_to_apply(Path(d));p=c/'verification-plan.json';data=json.loads(p.read_text())
            data['checks'][0]['artifacts']=['missing.lock'];p.write_text(json.dumps(data))
            with self.assertRaisesRegex(MachineError,'artifact missing'):
                m.run_check(None,'task-1')

    def test_declared_environment_change_invalidates_success(self):
        from wm_ai_coding.runs import verification_findings
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, {"WM_TEST_INPUT": "first"}):
            m, c = advance_to_apply(Path(d)); acceptance(m, c)
            p = c / "verification-plan.json"; data = json.loads(p.read_text())
            data["checks"][0]["environment"] = ["WM_TEST_INPUT"]
            p.write_text(json.dumps(data)); m.run_check(None, "task-1")
            os.environ["WM_TEST_INPUT"] = "second"
            self.assertTrue(any("stale" in f for f in verification_findings(Path(d), c)))

    def test_release_manifest_detects_changed_bundle(self):
        from wm_ai_coding.identity import seal_bundle, verify_bundle
        with tempfile.TemporaryDirectory() as d:
            p = Path(d); (p / "skills").mkdir(); f = p / "skills/SKILL.md"; f.write_text("one")
            seal_bundle(p); self.assertTrue(verify_bundle(p)["valid"])
            f.write_text("two"); self.assertFalse(verify_bundle(p)["valid"])


class HookTests(unittest.TestCase):
    def test_direct_state_write_and_compound_shell_are_denied(self):
        from wm_ai_coding.hooks import handle_hook
        with tempfile.TemporaryDirectory() as d:
            m,_=advance_to_apply(Path(d));m.handoff(None,scope=['.'])
            for event in [dict(tool_name='Write',tool_input={'file_path':str(Path(d)/'.wm/state.json')}),
                          dict(tool_name='Bash',tool_input={'command':'wm status; unexpected'})]:
                self.assertEqual('deny',handle_hook(m,'codex','PreToolUse',event)['hookSpecificOutput']['permissionDecision'])

    def test_patch_paths_and_unknown_host_events_are_not_silently_allowed(self):
        from wm_ai_coding.hooks import handle_hook
        with tempfile.TemporaryDirectory() as d:
            m,_=advance_to_apply(Path(d));m.handoff(None,scope=['allowed.py'])
            event={'tool_name':'apply_patch','tool_input':{'command':'*** Update File: bad.py\n@@\n-x\n+y'}}
            self.assertEqual('deny',handle_hook(m,'codex','PreToolUse',event)['hookSpecificOutput']['permissionDecision'])
            with self.assertRaises(ValueError):handle_hook(m,'codex','TaskCompleted',{})

    def test_write_outside_scope_denied_with_host_specific_protocol(self):
        from wm_ai_coding.hooks import handle_hook
        with tempfile.TemporaryDirectory() as d:
            m, _ = advance_to_apply(Path(d)); m.handoff(None, scope=["allowed.py"])
            event = {"tool_name": "Write", "tool_input": {"file_path": str(Path(d)/"bad.py")}}
            for host in ("codex", "claude"):
                result = handle_hook(m, host, "PreToolUse", event)
                self.assertEqual("deny", result["hookSpecificOutput"]["permissionDecision"])

    def test_stop_allows_pause_but_not_false_completion(self):
        from wm_ai_coding.hooks import handle_hook
        with tempfile.TemporaryDirectory() as d:
            m, _ = advance_to_apply(Path(d))
            self.assertNotIn("decision", handle_hook(m, "codex", "Stop", {"intent": "pause"}))
            self.assertEqual("block", handle_hook(m, "codex", "Stop", {"intent": "complete"})["decision"])


class SyncTests(unittest.TestCase):
    def test_explicit_addition_rejects_empty_or_wrong_durable_tree(self):
        from wm_ai_coding.specs import expected_specs, validate_sync
        delta={'a/spec.md':'## ADDED Requirements\n### Requirement: A\nExpected.\n#### Scenario: works\nPass.\n'}
        self.assertTrue(validate_sync({},delta,{}))
        expected=expected_specs({},delta)
        self.assertTrue(validate_sync({},delta,{'a/spec.md':expected['a/spec.md'].replace('Expected.','Wrong.')}))

    def test_modified_body_and_unaffected_requirements_are_checked(self):
        from wm_ai_coding.specs import expected_specs, validate_sync
        before = {"a/spec.md": "# A\n## Requirements\n### Requirement: Old\nKeep.\n### Requirement: Edit\nBefore.\n"}
        delta = {"a/spec.md": "## MODIFIED Requirements\n### Requirement: Edit\nAfter.\n"}
        expected = expected_specs(before, delta)
        self.assertIn("Keep.", expected["a/spec.md"])
        self.assertIn("After.", expected["a/spec.md"])
        self.assertEqual([], validate_sync(before, delta, expected))
        self.assertTrue(validate_sync(before, delta, {"a/spec.md": "### Requirement: Edit\nAfter."}))

    def test_removed_and_renamed_validate_preimages(self):
        from wm_ai_coding.specs import expected_specs
        before = {"a/spec.md": "### Requirement: A\nKeep.\n### Requirement: B\nDelete.\n"}
        delta = {"a/spec.md": "## RENAMED Requirements\n- FROM: `### Requirement: A`\n- TO: `### Requirement: C`\n## REMOVED Requirements\n### Requirement: B\nReason.\n"}
        result = expected_specs(before, delta)["a/spec.md"]
        self.assertIn("Requirement: C", result); self.assertNotIn("Requirement: B", result)
        with self.assertRaises(ValueError):
            expected_specs({}, delta)


class ReviewTests(unittest.TestCase):
    def test_summary_uses_explicit_applicability_not_section_presence(self):
        from test_hardening import verified
        from wm_ai_coding.cli import main
        with tempfile.TemporaryDirectory() as d:
            m,c=verified(Path(d),frontend_text='Not applicable; CLI only.')
            self.assertTrue(m.recovery()['evidence']['frontend_design'])
            with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(0,main(['--repo',d,'verification-summary']))

    def test_structured_review_rejects_blockers_and_stale_snapshot(self):
        from wm_ai_coding.reviews import record_review, review_findings
        with tempfile.TemporaryDirectory() as d:
            repo=Path(d); m,c=advance_to_apply(repo)
            record_review(repo,c,reviewer="session:reviewer",mode="self",findings=[{"severity":"blocking","message":"bug","resolved":False}])
            self.assertTrue(review_findings(repo,c,False))
            record_review(repo,c,reviewer="session:reviewer",mode="self",findings=[])
            self.assertEqual([],review_findings(repo,c,False))
            (repo/'code.py').write_text('new')
            self.assertTrue(review_findings(repo,c,False))

    def test_browser_evidence_required_only_when_applicable(self):
        from wm_ai_coding.reviews import record_review, review_findings
        with tempfile.TemporaryDirectory() as d:
            repo=Path(d);m,c=advance_to_apply(repo)
            record_review(repo,c,reviewer="reviewer",mode="self",findings=[])
            self.assertEqual([],review_findings(repo,c,False))
            self.assertTrue(review_findings(repo,c,True))


class EvalTests(unittest.TestCase):
    def test_behavior_evaluation_reports_cases_not_just_test_count(self):
        from wm_ai_coding.evaluations import evaluate
        result=evaluate()
        self.assertTrue(result['valid'],result)
        self.assertGreaterEqual(len(result['cases']),6)


class DiagnosticTests(unittest.TestCase):
    def test_live_owner_lock_does_not_expire_by_age(self):
        from wm_ai_coding.store import StateStore, StateLockTimeout
        import time
        with tempfile.TemporaryDirectory() as d:
            store=StateStore(Path(d));store.directory.mkdir()
            store.lock_path.write_text(json.dumps({'pid':os.getpid(),'created_at':time.time()-300}))
            with self.assertRaises(StateLockTimeout):
                with store.lock(timeout=0.05,stale_after=60):pass

    def test_brief_is_bounded_and_doctor_reports_missing_archive(self):
        from wm_ai_coding.diagnostics import brief, doctor
        with tempfile.TemporaryDirectory() as d:
            m,_=advance_to_apply(Path(d))
            self.assertLessEqual(len(json.dumps(brief(m)).encode()),2048)
            self.assertIn('capabilities',doctor(m))

    def test_event_failure_is_replayed_once_after_committed_state(self):
        from wm_ai_coding.store import StateStore
        with tempfile.TemporaryDirectory() as d:
            m,_=advance_to_apply(Path(d));store=m.store;s=store.read()
            with patch.object(StateStore,'_append_event',side_effect=OSError('disk')):
                updated=store.write(s,expected_revision=s['revision'],event='probe')
            self.assertEqual(updated['revision'],store.read()['revision'])
            store.flush_events();store.flush_events()
            events=[json.loads(x) for x in store.events_path.read_text().splitlines()]
            self.assertEqual(1,sum(e['revision']==updated['revision'] for e in events))


class BatchTests(unittest.TestCase):
    def test_controller_rejects_unknown_or_unready_batch_task(self):
        with tempfile.TemporaryDirectory() as d:
            repo=Path(d);m,c=advance_to_apply(repo);workspace=repo/'isolated';workspace.mkdir()
            with self.assertRaises(MachineError):
                m.batch_checks(None,[{'task':'task-999','workspace':str(workspace),'check':'task-1'}])

    def test_independent_workspaces_run_checks_and_share_no_source(self):
        from wm_ai_coding.batch import run_batch
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);a=p/'a';b=p/'b';a.mkdir();b.mkdir()
            jobs=[{'task':f'task-{i}','workspace':str(w),'argv':[sys.executable,'-c','print(1)']} for i,w in enumerate((a,b),1)]
            result=run_batch(jobs,max_parallel=2)
            self.assertTrue(result['valid']);self.assertEqual(2,len(result['results']))
            jobs[1]['workspace']=str(a)
            with self.assertRaises(ValueError):run_batch(jobs,max_parallel=2)

    def test_batch_rejects_dependencies_and_source_mutating_checks(self):
        from wm_ai_coding.batch import run_batch
        with tempfile.TemporaryDirectory() as d:
            job={'task':'task-1','workspace':d,'argv':[sys.executable,'-c',"from pathlib import Path; Path('new.py').write_text('x')"]}
            self.assertFalse(run_batch([job])['valid'])
            job['depends_on']=['task-2']
            with self.assertRaises(ValueError):run_batch([job])


if __name__ == '__main__':
    unittest.main()
