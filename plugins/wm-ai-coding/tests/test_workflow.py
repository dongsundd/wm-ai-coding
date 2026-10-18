import sys
import tempfile
import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))

from wm_ai_coding.workflow import WorkflowError, load_workflow


class WorkflowTest(unittest.TestCase):
    def test_packaged_workflow_is_valid_and_ordered(self) -> None:
        workflow = load_workflow(PLUGIN_ROOT / "skills" / "using-wm" / "workflow.yaml")
        self.assertEqual("clarify", workflow.initial)
        self.assertEqual("impact", workflow.next_state("clarify"))
        self.assertEqual("close", workflow.next_state("verify"))
        self.assertTrue(workflow.states["close"].terminal)
        self.assertEqual(64, len(workflow.checksum))

    def test_unknown_transition_is_rejected(self) -> None:
        body = """schema_version: 1
name: bad
initial: one
states:
  one:
    next: missing
    skill: test
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workflow.yaml"
            path.write_text(body, encoding="utf-8")
            with self.assertRaises(WorkflowError):
                load_workflow(path)


if __name__ == "__main__":
    unittest.main()

