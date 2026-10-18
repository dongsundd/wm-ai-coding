import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))

from wm_ai_coding.machine import MachineError, StateMachine
from wm_ai_coding.store import RevisionConflict, StateStore
from wm_ai_coding.workflow import load_workflow


DESIGN = "# Design\n\n## CodeGraph impact analysis\n\nEvidence.\n"
TASKS = """# Tasks
### Task 1: Result
- [ ] Requirement: R1
- [ ] Outcome: Result.
- [ ] Files: `x.py`
- [ ] Interfaces — Consumes: none; Produces: x.
- [ ] Acceptance: x exists.
- [ ] Verification: `pytest`; expected PASS.
"""


class StateMachineRuntimeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        self.change = self.repo / "sdd" / "changes" / "sample"
        (self.change / "specs" / "runtime").mkdir(parents=True)
        (self.change / "proposal.md").write_text("proposal", encoding="utf-8")
        (self.change / "specs" / "runtime" / "spec.md").write_text("spec", encoding="utf-8")
        (self.change / "design.md").write_text(DESIGN, encoding="utf-8")
        (self.change / "tasks.md").write_text(TASKS, encoding="utf-8")
        self.workflow = load_workflow(PLUGIN_ROOT / "skills" / "using-wm" / "workflow.yaml")
        self.machine = StateMachine(self.repo, self.workflow)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_init_creates_ignored_multi_change_state_idempotently(self) -> None:
        first = self.machine.init()
        second = self.machine.init()
        self.assertEqual("sample", first["active_change"])
        self.assertIn("sample", first["changes"])
        self.assertEqual(first["revision"], second["revision"])
        gitignore = (self.repo / ".gitignore").read_text(encoding="utf-8")
        self.assertEqual(1, gitignore.count("# BEGIN WM AI CODING"))
        self.assertTrue((self.repo / ".wm" / "state.json").is_file())

    def test_init_upgrades_managed_gitignore_after_state_exists(self) -> None:
        self.machine.init()
        (self.repo / ".gitignore").write_text(
            "custom-rule\n# BEGIN WM AI CODING\n.wm/\n# END WM AI CODING\n",
            encoding="utf-8",
        )

        result = self.machine.init()

        gitignore = (self.repo / ".gitignore").read_text(encoding="utf-8")
        self.assertTrue(gitignore.startswith("custom-rule\n"))
        self.assertEqual(1, gitignore.count("# BEGIN WM AI CODING"))
        self.assertIn("/sdd/changes/*", gitignore)
        self.assertIn("!/sdd/changes/archive/**/*", gitignore)
        self.assertIn("/sdd/changes/archive/**/tasks.md", gitignore)
        self.assertTrue(result["maintenance"]["gitignore_changed"])
        self.assertFalse(self.machine.init()["maintenance"]["gitignore_changed"])

    def test_init_untracks_only_ignored_sdd_files_and_keeps_them_local(self) -> None:
        self.machine.init()
        archive = self.repo / "sdd" / "changes" / "archive" / "done"
        archive.mkdir(parents=True)
        files = {
            "sdd/changes/sample/proposal.md": self.change / "proposal.md",
            "sdd/changes/archive/done/proposal.md": archive / "proposal.md",
            "sdd/changes/archive/done/tasks.md": archive / "tasks.md",
            "sdd/changes/archive/done/verification.md": archive / "verification.md",
        }
        for path in files.values():
            path.write_text(path.name, encoding="utf-8")
        with (self.repo / ".gitignore").open("a", encoding="utf-8") as gitignore:
            gitignore.write("/sdd/changes/archive/**/proposal.md\n")
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True)
        subprocess.run(["git", "add", "-f", "sdd/changes"], cwd=self.repo, check=True)

        result = self.machine.init()

        tracked = subprocess.run(
            ["git", "ls-files"], cwd=self.repo, check=True, capture_output=True, text=True
        ).stdout.splitlines()
        self.assertEqual(["sdd/changes/archive/done/proposal.md"], tracked)
        self.assertEqual(
            [
                "sdd/changes/archive/done/tasks.md",
                "sdd/changes/archive/done/verification.md",
                "sdd/changes/sample/design.md",
                "sdd/changes/sample/proposal.md",
                "sdd/changes/sample/specs/runtime/spec.md",
                "sdd/changes/sample/tasks.md",
            ],
            result["maintenance"]["untracked_files"],
        )
        self.assertTrue(all(path.is_file() for path in files.values()))
        self.assertEqual([], self.machine.init()["maintenance"]["untracked_files"])

    def test_validate_reports_incomplete_managed_ignore_policy(self) -> None:
        self.machine.init()
        (self.repo / ".gitignore").write_text(".wm/\n", encoding="utf-8")

        result = self.machine.validate()

        self.assertFalse(result["valid"])
        self.assertIn("WM managed .gitignore policy is missing or incomplete", result["findings"])

    def test_approval_and_baseline_become_stale_after_artifact_change(self) -> None:
        self.machine.init()
        self.machine.approve_design("sample")
        self.machine.baseline_tasks("sample")
        (self.change / "design.md").write_text(DESIGN + "changed", encoding="utf-8")
        (self.change / "tasks.md").write_text(TASKS + "changed", encoding="utf-8")
        state = self.machine.reconcile("sample")
        change = state["changes"]["sample"]
        self.assertEqual("stale", change["approvals"]["design"]["status"])
        self.assertEqual("stale", change["baselines"]["tasks"]["status"])
        self.assertEqual("drifted", change["status"])

    def test_task_checkbox_progress_does_not_invalidate_baseline(self) -> None:
        self.machine.init()
        self.machine.baseline_tasks("sample")
        (self.change / "tasks.md").write_text(TASKS.replace("- [ ]", "- [x]"), encoding="utf-8")
        state = self.machine.reconcile("sample")
        self.assertEqual("current", state["changes"]["sample"]["baselines"]["tasks"]["status"])

    def test_status_does_not_advance_and_rewind_is_explicit(self) -> None:
        self.machine.init()
        before = self.machine.status("sample")
        after = self.machine.status("sample")
        self.assertEqual(before["revision"], after["revision"])
        self.machine.approve_design("sample")
        self.machine.baseline_tasks("sample")
        advanced = self.machine.advance("sample")
        self.assertEqual("impact", advanced["changes"]["sample"]["stage"])
        rewound = self.machine.rewind("sample", "clarify", "requirements changed")
        self.assertEqual("clarify", rewound["changes"]["sample"]["stage"])
        self.assertEqual({}, rewound["changes"]["sample"]["approvals"])

    def test_store_rejects_stale_revision(self) -> None:
        self.machine.init()
        store = StateStore(self.repo)
        state = store.read()
        store.write(state, expected_revision=state["revision"])
        with self.assertRaises(RevisionConflict):
            store.write(state, expected_revision=state["revision"])


if __name__ == "__main__":
    unittest.main()
