import re
import unittest
from pathlib import Path

import yaml


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = PLUGIN_ROOT / "skills"
PROFILES = ("harmonyos-ai-coding", "python-ai-coding", "rust-ai-coding")
ALLOWED_FRONTMATTER = {"name", "description"}


def read_skill(name: str) -> tuple[dict[str, object], str]:
    body = (SKILLS_ROOT / name / "SKILL.md").read_text(encoding="utf-8")
    match = re.match(r"\A---\s*\n(.*?)\n---\s*\n", body, re.DOTALL)
    if not match:
        raise AssertionError(f"{name}: missing YAML frontmatter")
    return yaml.safe_load(match.group(1)), body[match.end():]


class StackProfileContractTest(unittest.TestCase):
    def test_each_profile_is_valid_and_has_ui_metadata(self) -> None:
        for name in PROFILES:
            with self.subTest(profile=name):
                metadata, body = read_skill(name)
                self.assertEqual(ALLOWED_FRONTMATTER, set(metadata))
                self.assertEqual(name, metadata["name"])
                self.assertLess(len(body.splitlines()), 500)
                self.assertTrue((SKILLS_ROOT / name / "agents" / "openai.yaml").is_file())

    def test_profiles_are_overlays_not_independent_workflows(self) -> None:
        for name in PROFILES:
            with self.subTest(profile=name):
                _, body = read_skill(name)
                self.assertIn("using-wm", body)
                self.assertIn("continuous execution", body)
                self.assertIn("repository", body.lower())

    def test_harness_selects_and_records_profiles_without_task_pauses(self) -> None:
        harness = (SKILLS_ROOT / "using-wm" / "SKILL.md").read_text(encoding="utf-8")
        workflow = (SKILLS_ROOT / "using-wm" / "references" / "workflow.md").read_text(encoding="utf-8")
        combined = harness + "\n" + workflow
        self.assertIn("Technology profile selection", combined)
        self.assertIn("harmonyos-ai-coding", combined)
        self.assertIn("python-ai-coding", combined)
        self.assertIn("rust-ai-coding", combined)
        self.assertIn("frontend-design", combined)
        self.assertIn("frontend_surface_changed", combined)
        self.assertIn("Web or app page", combined)
        self.assertIn("Do not pause between tasks", combined)

    def test_frontend_design_is_a_design_stage_skill_not_an_implementation_profile(self) -> None:
        metadata, body = read_skill("frontend-design")
        self.assertEqual("frontend-design", metadata["name"])
        self.assertTrue((SKILLS_ROOT / "frontend-design" / "agents" / "openai.yaml").is_file())
        self.assertIn("`using-wm`", body)
        self.assertIn("## Frontend design", body)
        self.assertIn("Do not modify product code", body)
        self.assertIn("before task decomposition", body)
        self.assertNotIn("Implement faithfully", body)
        self.assertFalse((SKILLS_ROOT / "web-ai-coding").exists())


if __name__ == "__main__":
    unittest.main()
