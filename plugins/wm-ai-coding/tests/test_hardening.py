from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_runtime import advance_to_apply, complete_task, machine_for, write_change, advance_stage, accept_task
from wm_ai_coding.machine import MachineError


def plan_for(change: Path, argv: list[str] | None = None) -> None:
    (change / "verification-plan.json").write_text(json.dumps({
        "checks": [{"id": "suite", "argv": argv or [sys.executable, "-c", "print('passed')"],
                    "requirements": ["capability::R1"], "scenarios": ["capability::R1::success"]}]
    }), encoding="utf-8")


def verified(repo: Path, frontend_text: str = ""):
    machine, change = advance_to_apply(repo,frontend_text)
    for index in (1,2):
        accept_task(machine,change,index);machine.advance()
    plan_for(change)
    handoff=machine.handoff(None,scope=["sdd"])
    record=machine.run_check(None,"suite")
    (change/"verification.md").write_text("Ready for archive.\n",encoding="utf-8")
    from wm_ai_coding.reviews import record_review
    record_review(repo,change,reviewer="fixture-review",mode="self",findings=[])
    (change/"verification.json").write_text(json.dumps({"schema_version":1,"status":"passed","coverage":{
        "capability::R1":[record["id"]],"capability::R1::success":[record["id"]]}}))
    machine.finish_handoff(None,handoff["id"],"completed",["sdd/changes/c1/verification.md"])
    return machine,change


class FreshGateTests(unittest.TestCase):
    def test_advance_checks_changed_design_without_reconcile(self):
        with tempfile.TemporaryDirectory() as directory:
            machine, change = advance_to_apply(Path(directory))
            with (change / "design.md").open("a", encoding="utf-8") as handle:
                handle.write("\nA changed decision.\n")
            with self.assertRaisesRegex(MachineError, "design_approved"):
                machine.advance()

    def test_delta_spec_edit_invalidates_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            machine, change = advance_to_apply(Path(directory))
            (change / "specs/capability/spec.md").write_text("Changed requirement", encoding="utf-8")
            with self.assertRaisesRegex(MachineError, "design_approved"):
                machine.advance()

    def test_frontend_condition_requires_owned_section(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            write_change(repo)
            machine = machine_for(repo)
            machine.init(gitignore=False)
            advance_stage(machine)
            machine.set_frontend(None, True)
            with self.assertRaisesRegex(MachineError, "frontend"):
                machine.approve_design(reference="test:user-request")

    def test_missing_approval_provenance_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            write_change(repo)
            machine = machine_for(repo)
            machine.init(gitignore=False)
            with self.assertRaisesRegex(MachineError, "reference"):
                machine.approve_design()

    def test_change_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            machine = machine_for(repo)
            machine.init(gitignore=False)
            with self.assertRaises(MachineError):
                machine.reconcile("../../outside")

    def test_reconcile_preserves_blocker_during_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            machine, change = advance_to_apply(Path(directory))
            machine.block(None, "waiting for decision")
            (change / "design.md").write_text("Changed", encoding="utf-8")
            state = machine.reconcile()
            self.assertEqual("blocked", state["changes"]["c1"]["status"])


class ExecutedEvidenceTests(unittest.TestCase):
    def test_report_alone_cannot_pass_verify(self):
        with tempfile.TemporaryDirectory() as directory:
            machine, change = advance_to_apply(Path(directory))
            for index in (1, 2):
                accept_task(machine, change, index)
                machine.advance()
            (change / "verification.md").write_text("Ready for archive.", encoding="utf-8")
            with self.assertRaisesRegex(MachineError, "verification"):
                machine.advance()

    def test_run_is_bound_to_current_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            machine, change = verified(repo)
            (repo / "source.py").write_text("changed = True", encoding="utf-8")
            with self.assertRaisesRegex(MachineError, "verification"):
                machine.advance()

    def test_failed_run_does_not_reuse_prior_success(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            machine, change = verified(repo)
            plan_for(change, [sys.executable, "-c", "raise SystemExit(3)"])
            result = machine.run_check(None, "suite")
            self.assertEqual(3, result["exit_code"])
            with self.assertRaisesRegex(MachineError, "verification"):
                machine.advance()

    def test_uncovered_scenario_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            machine, change = verified(Path(directory))
            with (change / "specs/capability/spec.md").open("a", encoding="utf-8") as handle:
                handle.write("\n#### Scenario: failure\nReject.\n")
            packet = machine.recovery()
            self.assertTrue(any("failure" in finding for finding in packet["verification_findings"]))

    def test_successful_current_run_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            machine, _ = verified(Path(directory))
            self.assertEqual("close", machine.advance()["changes"]["c1"]["stage"])

    def test_timeout_is_recorded(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            machine, change = advance_to_apply(repo)
            plan_for(change, [sys.executable, "-c", "import time; time.sleep(10)"])
            result = machine.run_check(None, "suite", timeout=0.05)
            self.assertEqual("timed_out", result["status"])


class HandoffTests(unittest.TestCase):
    def test_completed_handoff_requires_task_acceptance(self):
        with tempfile.TemporaryDirectory() as directory:
            machine, _ = advance_to_apply(Path(directory))
            handoff = machine.handoff(None, scope=["sdd/changes/c1/tasks.md"])
            with self.assertRaisesRegex(MachineError, "acceptance"):
                machine.finish_handoff(None, handoff["id"], "completed", ["sdd/changes/c1/tasks.md"])

    def test_output_outside_handoff_scope_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            machine, change = advance_to_apply(Path(directory))
            handoff = machine.handoff(None, scope=["source.py"])
            complete_task(change / "tasks.md", 1)
            with self.assertRaisesRegex(MachineError, "scope"):
                machine.finish_handoff(None, handoff["id"], "completed", ["sdd/changes/c1/tasks.md"])

    def test_successful_handoff_and_next_task(self):
        with tempfile.TemporaryDirectory() as directory:
            machine, change = advance_to_apply(Path(directory))
            handoff = machine.handoff(None, scope=["sdd/changes/c1/tasks.md"])
            machine.run_check(None,"task-1")
            complete_task(change / "tasks.md", 1)
            machine.finish_handoff(None, handoff["id"], "completed", ["sdd/changes/c1/tasks.md"])
            state = machine.advance()
            self.assertEqual(2, state["changes"]["c1"]["current_task"]["index"])

    def test_running_handoff_blocks_advance_and_recovers(self):
        with tempfile.TemporaryDirectory() as directory:
            machine, _ = advance_to_apply(Path(directory))
            handoff = machine.handoff(None, scope=["src/auth.py"])
            packet = machine.recovery()
            self.assertEqual(handoff["id"], packet["handoff"]["id"])
            with self.assertRaisesRegex(MachineError, "handoff"):
                machine.advance()

    def test_handoff_rejects_stale_id_and_missing_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            machine, _ = advance_to_apply(Path(directory))
            handoff = machine.handoff(None, scope=["src/auth.py"])
            with self.assertRaises(MachineError):
                machine.finish_handoff(None, "wrong", "completed", ["sdd/changes/c1/tasks.md"])
            with self.assertRaises(MachineError):
                machine.finish_handoff(None, handoff["id"], "completed", ["missing.py"])

    def test_handoff_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            machine, _ = advance_to_apply(Path(directory))
            machine.handoff(None, scope=["src/auth.py"])
            with self.assertRaises(MachineError):
                machine.handoff(None, scope=["other.py"])


class ArchiveTests(unittest.TestCase):
    def prepare(self, repo):
        machine, change = verified(repo)
        machine.advance()
        machine.sync_specs()
        advance_stage(machine)
        machine.handoff(None,scope=["sdd/changes"])
        return machine, change

    def test_archive_is_idempotent_and_validate_uses_archive_path(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            machine, change = self.prepare(repo)
            state = machine.archive(None)
            self.assertFalse(change.exists())
            self.assertEqual("archived", state["changes"]["c1"]["status"])
            self.assertIsNone(state["active_change"])
            self.assertEqual(state, machine.archive("c1"))
            self.assertFalse(any("missing change" in f for f in machine.validate()["findings"]))

    def test_archive_recovers_after_rename_before_state_commit(self):
        with tempfile.TemporaryDirectory() as directory:
            machine, change = self.prepare(Path(directory))
            original = machine._write

            def interrupt(state, revision, event):
                if event == "archived":
                    raise RuntimeError("simulated interruption")
                return original(state, revision, event)

            with patch.object(machine, "_write", side_effect=interrupt):
                with self.assertRaises(RuntimeError):
                    machine.archive(None)
            self.assertFalse(change.exists())
            state = machine.archive("c1")
            self.assertEqual("archived", state["changes"]["c1"]["status"])

    def test_archive_rechecks_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            machine, _ = self.prepare(repo)
            (repo / "source.py").write_text("new change", encoding="utf-8")
            with self.assertRaisesRegex(MachineError, "verification"):
                machine.archive(None)


class ReviewRegressionTests(unittest.TestCase):
    def test_empty_task_field_cannot_consume_next_line(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            machine, change = advance_to_apply(repo)
            path = change / "tasks.md"
            path.write_text(path.read_text().replace("Requirement: R1", "Requirement: "), encoding="utf-8")
            from wm_ai_coding.evidence import inspect_change
            self.assertFalse(inspect_change(change)["task_contract_valid"])

    def test_negative_archive_readiness_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            machine, change = verified(Path(directory))
            (change / "verification.md").write_text("Not ready for archive. 2 critical issues.", encoding="utf-8")
            with self.assertRaisesRegex(MachineError, "verification"):
                machine.advance()

    def test_recovery_after_archive_move_has_current_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            machine, _ = ArchiveTests().prepare(Path(directory))
            original = machine._write

            def interrupt(state, revision, event):
                if event == "archived":
                    raise RuntimeError("interrupted")
                return original(state, revision, event)

            with patch.object(machine, "_write", side_effect=interrupt):
                with self.assertRaises(RuntimeError):
                    machine.archive(None)
            packet = machine.recovery()
            self.assertEqual([], packet["missing_gates"])
            self.assertEqual([], packet["verification_findings"])

    def test_reconcile_recovers_pending_archive_instead_of_missing_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            machine, _ = ArchiveTests().prepare(Path(directory))
            original = machine._write

            def interrupt(state, revision, event):
                if event == "archived":
                    raise RuntimeError("interrupted")
                return original(state, revision, event)

            with patch.object(machine, "_write", side_effect=interrupt):
                with self.assertRaises(RuntimeError):
                    machine.archive(None)
            machine.reconcile("c1")
            self.assertEqual("archive", machine.recovery()["next_action"])

    def test_archive_recovery_refuses_changed_json_attachment(self):
        with tempfile.TemporaryDirectory() as directory:
            machine, _ = ArchiveTests().prepare(Path(directory))
            original = machine._write

            def interrupt(state, revision, event):
                if event == "archived":
                    raise RuntimeError("interrupted")
                return original(state, revision, event)

            with patch.object(machine, "_write", side_effect=interrupt):
                with self.assertRaises(RuntimeError):
                    machine.archive(None)
            state = machine._read()
            target = machine.repo / state["changes"]["c1"]["archive_intent"]["target"]
            (target / "attachment.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(MachineError):
                machine.archive("c1")

    def test_workflow_rejects_cycles(self):
        from wm_ai_coding.workflow import WorkflowError, load_workflow
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workflow.yaml"
            path.write_text("schema_version: 1\ninitial: a\nstates:\n  a:\n    skill: x\n    next: a\n", encoding="utf-8")
            with self.assertRaises(WorkflowError):
                load_workflow(path)

    def test_current_check_that_mutates_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            machine, change = verified(Path(directory))
            plan_for(change, [sys.executable, "-c", "from pathlib import Path; Path('new.py').write_text('new')"])
            machine.run_check(None, "suite")
            with self.assertRaisesRegex(MachineError, "verification"):
                machine.advance()

    def test_task_dependency_selects_ready_task(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            change = write_change(repo)
            tasks = change / "tasks.md"
            tasks.write_text(tasks.read_text().replace("### Task 1: Deliver outcome 1", "### Task 1: Deliver outcome 1\n- Depends on: task-2"), encoding="utf-8")
            machine = machine_for(repo)
            machine.init(gitignore=False)
            advance_stage(machine)
            machine.set_frontend(None, False)
            machine.approve_design(reference="test:user-request")
            advance_stage(machine)
            machine.baseline_tasks()
            state = advance_stage(machine)
            self.assertEqual(2, state["changes"]["c1"]["current_task"]["index"])

    def test_cyclic_tasks_cannot_be_baselined(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            change = write_change(repo)
            tasks = change / "tasks.md"
            tasks.write_text(tasks.read_text().replace("### Task 1: Deliver outcome 1", "### Task 1: Deliver outcome 1\n- Depends on: task-2").replace("### Task 2: Deliver outcome 2", "### Task 2: Deliver outcome 2\n- Depends on: task-1"), encoding="utf-8")
            machine = machine_for(repo)
            machine.init(gitignore=False)
            advance_stage(machine)
            machine.set_frontend(None, False)
            machine.approve_design(reference="test:user-request")
            advance_stage(machine)
            with self.assertRaisesRegex(MachineError, "task contract"):
                machine.baseline_tasks()

    def test_cli_failed_check_has_nonzero_exit(self):
        import contextlib
        import io
        from wm_ai_coding.cli import main
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            machine, change = advance_to_apply(repo)
            plan_for(change, [sys.executable, "-c", "raise SystemExit(1)"])
            with contextlib.redirect_stdout(io.StringIO()):
                result = main(["--repo", str(repo), "check", "suite"])
            self.assertNotEqual(0, result)


if __name__ == "__main__":
    unittest.main()
