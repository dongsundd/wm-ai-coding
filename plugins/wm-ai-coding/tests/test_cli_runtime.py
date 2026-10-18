import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))

from wm_ai_coding.cli import main


class CliRuntimeTest(unittest.TestCase):
    def test_init_status_block_and_resume_emit_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            change = repo / "sdd" / "changes" / "sample"
            change.mkdir(parents=True)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(0, main(["--repo", str(repo), "init"]))
            self.assertEqual("sample", json.loads(output.getvalue())["active_change"])

            for arguments, expected in (
                (["block", "--reason", "waiting"], "blocked"),
                (["resume"], "ready"),
            ):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    self.assertEqual(0, main(["--repo", str(repo), *arguments]))
                self.assertEqual(expected, json.loads(output.getvalue())["changes"]["sample"]["status"])

            before = json.loads((repo / ".wm" / "state.json").read_text(encoding="utf-8"))["revision"]
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(0, main(["--repo", str(repo), "status"]))
            after = json.loads((repo / ".wm" / "state.json").read_text(encoding="utf-8"))["revision"]
            self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()

