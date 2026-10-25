from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path


from support.paths import PLUGIN_ROOT

from wm_ai_coding.commands.workflow import main
from wm_ai_coding.lifecycle.machine import MachineError, StateMachine
from wm_ai_coding.infrastructure.store import StateLockTimeout, StateStore
from wm_ai_coding.infrastructure.workflow import load_workflow



from support.runtime import TASKS_TEMPLATE, accept_task, advance_stage, advance_to_apply, complete_supports, complete_task, machine_for, write_change

class WorkflowShowTest(unittest.TestCase):
    def test_workflow_show_serializes_conditional_skills(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = main(["workflow", "show"])
        self.assertEqual(0, code)
        payload = json.loads(stdout.getvalue())
        self.assertEqual("clarify", payload["initial"])
        self.assertEqual("frontend-design", payload["states"]["specify"]["conditional_skills"][0]["skill"])


class GateTest(unittest.TestCase):
    def test_empty_verification_report_does_not_satisfy_gate(self) -> None:
        from support.verification import verified
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            machine, change = verified(repo)
            (change / "verification.md").write_text("   \n", encoding="utf-8")
            with self.assertRaisesRegex(MachineError, "verification"):
                machine.advance()

    def test_critical_verification_report_does_not_satisfy_gate(self) -> None:
        from support.verification import verified
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            machine, change = verified(repo)
            (change / "verification.md").write_text(
                "## Verification Report: c1\n\n2 critical issue(s) found. Fix before archiving.\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(MachineError, "verification"):
                machine.advance()

    def test_partially_verified_report_does_not_satisfy_gate(self) -> None:
        from support.verification import verified
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            machine, change = verified(repo)
            (change / "verification.md").write_text(
                "## Verification Report: c1\n\n"
                "No critical issues found in the checks that ran. "
                "Full suite not verified: dependency unavailable.\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(MachineError, "verification"):
                machine.advance()

    def test_non_empty_verification_report_satisfies_gate(self) -> None:
        from support.verification import verified
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            machine, change = verified(repo)
            (change / "verification.md").write_text(
                "## Verification Report: c1\n\nAll checks passed. Ready for archive.\n",
                encoding="utf-8",
            )
            state = machine.advance()
            self.assertEqual("close", state["changes"]["c1"]["stage"])

    def test_approve_design_rejects_empty_design(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            change = write_change(repo)
            (change / "design.md").write_text("  \n", encoding="utf-8")
            machine = machine_for(repo)
            machine.init(gitignore=False)
            with self.assertRaisesRegex(MachineError, "design"):
                machine.approve_design()

    def test_planning_artifacts_require_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            change = write_change(repo)
            (change / "proposal.md").write_text("", encoding="utf-8")
            (change / "design.md").write_text("", encoding="utf-8")
            (change / "specs" / "capability" / "spec.md").write_text("", encoding="utf-8")
            machine = machine_for(repo)
            machine.init(gitignore=False)
            machine.rewind(None, "specify", "test")
            with self.assertRaisesRegex(MachineError, "planning_artifacts"):
                machine.advance()

    def test_design_requires_structural_analysis_before_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            change = write_change(repo)
            (change / "design.md").write_text(
                "# Design\n\nUse the existing path without structural evidence.\n",
                encoding="utf-8",
            )
            machine = machine_for(repo)
            machine.init(gitignore=False)
            advance_stage(machine)
            machine.set_frontend(None, False)
            machine.approve_design(reference="test:user-request")
            with self.assertRaisesRegex(MachineError, "structural_analysis"):
                machine.advance()


class GitignoreTest(unittest.TestCase):
    def test_crlf_managed_block_is_not_duplicated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            seeded = (
                "# BEGIN WM AI CODING\r\n.wm/\r\n# END WM AI CODING\r\n/.idea\r\n"
            )
            (repo / ".gitignore").write_text(seeded, encoding="utf-8", newline="")
            machine = machine_for(repo)
            machine.init()
            machine.init()
            content = (repo / ".gitignore").read_text(encoding="utf-8")
            self.assertEqual(1, content.count("# BEGIN WM AI CODING"))
            self.assertEqual(1, content.count(".wm/"))
            self.assertIn("/.idea", content)
            self.assertNotIn("\r\n", content)

    def test_legacy_block_is_replaced_and_custom_rules_kept(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            (repo / ".gitignore").write_text(
                "# BEGIN WM AI CODING\n.wm/\n# END WM AI CODING\n/custom-rule\n",
                encoding="utf-8",
            )
            machine = machine_for(repo)
            machine.init()
            content = (repo / ".gitignore").read_text(encoding="utf-8")
            self.assertEqual(1, content.count("# BEGIN WM AI CODING"))
            self.assertIn("/custom-rule", content)
            self.assertIn("!/sdd/changes/archive/", content)

    def test_init_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            machine = machine_for(repo)
            machine.init()
            first = (repo / ".gitignore").read_text(encoding="utf-8")
            machine.init()
            second = (repo / ".gitignore").read_text(encoding="utf-8")
            self.assertEqual(first, second)


class MigrationTest(unittest.TestCase):
    def test_migrate_remaps_legacy_impact_stage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            write_change(repo)
            machine = machine_for(repo)
            machine.init(gitignore=False)
            state_path = repo / ".wm" / "state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["workflow"]["checksum"] = "stale"
            state["changes"]["c1"]["stage"] = "impact"
            state_path.write_text(json.dumps(state), encoding="utf-8")
            migrated = machine.migrate()
            self.assertEqual("specify", migrated["changes"]["c1"]["stage"])
            self.assertEqual(machine.workflow.checksum, migrated["workflow"]["checksum"])
            self.assertEqual("specify", machine.status()["changes"]["c1"]["stage"])

    def test_migrate_rejects_unknown_stage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            write_change(repo)
            machine = machine_for(repo)
            machine.init(gitignore=False)
            state_path = repo / ".wm" / "state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["workflow"]["checksum"] = "stale"
            state["changes"]["c1"]["stage"] = "bogus"
            state_path.write_text(json.dumps(state), encoding="utf-8")
            with self.assertRaises(MachineError):
                machine.migrate()


class TaskLoopTest(unittest.TestCase):
    def test_apply_refuses_changed_task_definition_without_rebaseline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            machine, change = advance_to_apply(repo)
            tasks = change / "tasks.md"
            tasks.write_text(
                tasks.read_text(encoding="utf-8").replace("Deliver outcome 1", "Changed outcome 1"),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(MachineError, "baseline"):
                machine.advance()

    def test_apply_advance_tracks_one_task_at_a_time(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            machine, change = advance_to_apply(repo)
            state = machine.status()
            item = state["changes"]["c1"]
            self.assertEqual("apply", item["stage"])
            self.assertEqual({"index": 1, "id": "task-1", "title": "Task 1: Deliver outcome 1"}, item["current_task"])

            tasks = change / "tasks.md"
            accept_task(machine, change, 1)
            state = machine.advance()
            item = state["changes"]["c1"]
            self.assertEqual("apply", item["stage"])
            self.assertEqual({"index": 2, "id": "task-2", "title": "Task 2: Deliver outcome 2"}, item["current_task"])

            with self.assertRaisesRegex(MachineError, "handoff|current task"):
                machine.advance()

            accept_task(machine, change, 2)
            state = machine.advance()
            item = state["changes"]["c1"]
            self.assertEqual("verify", item["stage"])
            self.assertIsNone(item["current_task"])


class ReconcileTest(unittest.TestCase):
    def test_design_drift_rewinds_to_specify(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            machine, change = advance_to_apply(repo)
            (change / "design.md").write_text("# Design\n\nChanged design.\n", encoding="utf-8")
            state = machine.reconcile()
            item = state["changes"]["c1"]
            self.assertEqual("specify", item["stage"])
            self.assertEqual("ready", item["status"])
            self.assertEqual("specify", item["required_stage"])
            self.assertEqual("stale", item["approvals"]["design"]["status"])


class LockTest(unittest.TestCase):
    def test_stale_lock_is_recovered(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = StateStore(Path(directory))
            store.directory.mkdir()
            store.lock_path.write_text(
                json.dumps({"pid": 999999, "created_at": time.time() - 120}),
                encoding="utf-8",
            )
            old = time.time() - 120
            os.utime(store.lock_path, (old, old))
            with store.lock(timeout=0.5, stale_after=60):
                self.assertTrue(store.lock_path.exists())

    def test_fresh_lock_still_times_out(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = StateStore(Path(directory))
            store.directory.mkdir()
            store.lock_path.write_text(
                json.dumps({"pid": os.getpid(), "created_at": time.time()}),
                encoding="utf-8",
            )
            with self.assertRaises(StateLockTimeout):
                with store.lock(timeout=0.1, stale_after=60):
                    pass


class WorkflowShapeTest(unittest.TestCase):
    def test_close_syncs_before_archive(self) -> None:
        workflow = load_workflow(PLUGIN_ROOT / "skills" / "development-workflow" / "config" / "workflow.yaml")
        self.assertEqual("specification-sync", workflow.states["close"].skill)
        self.assertEqual("archive", workflow.states["close"].next)
        self.assertEqual("change-archive", workflow.states["archive"].skill)
        self.assertTrue(workflow.states["archive"].terminal)

    def test_close_requires_synced_specs_snapshot(self) -> None:
        from support.verification import verified
        from wm_ai_coding.lifecycle.specs import expected_specs
        with tempfile.TemporaryDirectory() as directory:
            repo=Path(directory);machine,change=verified(repo)
            machine.advance()
            expected=expected_specs({}, {"capability/spec.md": (change/"specs/capability/spec.md").read_text()})
            durable=repo/"sdd/specs/capability/spec.md";durable.parent.mkdir(parents=True)
            durable.write_text(expected["capability/spec.md"])
            with self.assertRaisesRegex(MachineError,"specs_synced"):
                machine.advance()
            machine.baseline_specs()
            state=advance_stage(machine)
            self.assertEqual("archive",state["changes"]["c1"]["stage"])



if __name__ == "__main__":
    unittest.main()
