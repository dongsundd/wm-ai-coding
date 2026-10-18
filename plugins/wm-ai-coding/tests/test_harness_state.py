import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "using-wm"
    / "scripts"
    / "harness_state.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("harness_state", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


VALID_TASK = """# Tasks

### Task 1: Add one result
- [ ] Requirement: `REQ-1`
- [ ] Outcome: One observable result.
- [ ] Files: `src/result.py`, `tests/test_result.py`
- [ ] Interfaces — Consumes: none; Produces: `result()`.
- [ ] Acceptance: Calling `result()` returns the specified value.
- [ ] Verification: `pytest tests/test_result.py -q`; expected PASS.
"""


class HarnessStateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.change = Path(self.temp.name) / "sdd" / "changes" / "sample"
        self.change.mkdir(parents=True)
        self.module = load_module()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write(self, relative: str, body: str = "x") -> None:
        path = self.change / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")

    def prepare_design(self) -> None:
        self.write("proposal.md")
        self.write("specs/workflow/spec.md")
        self.write(
            "design.md",
            "# Design\n\n## CodeGraph impact analysis\n\nEvidence.\n",
        )

    def test_missing_codegraph_blocks_task_stage(self) -> None:
        self.write("proposal.md")
        self.write("specs/workflow/spec.md")
        self.write("design.md", "# Design\n")
        result = self.module.inspect(self.change)
        self.assertEqual("impact", result["next_stage"])
        self.assertIn("codegraph_impact", result["missing_gates"])

    def test_invalid_task_contract_blocks_apply(self) -> None:
        self.prepare_design()
        self.write("tasks.md", "### Task 1: Do everything\n- [ ] Implement it all\n")
        result = self.module.inspect(self.change)
        self.assertEqual("tasks", result["next_stage"])
        self.assertFalse(result["tasks"]["contract_valid"])
        self.assertTrue(result["tasks"]["contract_findings"])

    def test_valid_open_task_is_ready_for_apply(self) -> None:
        self.prepare_design()
        self.write("tasks.md", VALID_TASK)
        result = self.module.inspect(self.change)
        self.assertEqual("apply", result["next_stage"])
        self.assertTrue(result["tasks"]["contract_valid"])
        self.assertEqual(1, result["tasks"]["open"])
        self.assertEqual(0, result["tasks"]["completed"])

    def test_completed_tasks_advance_to_verify(self) -> None:
        self.prepare_design()
        self.write("tasks.md", VALID_TASK.replace("- [ ]", "- [x]"))
        result = self.module.inspect(self.change)
        self.assertEqual("verify", result["next_stage"])
        self.assertEqual(0, result["tasks"]["open"])
        self.assertEqual(1, result["tasks"]["completed"])


if __name__ == "__main__":
    unittest.main()
