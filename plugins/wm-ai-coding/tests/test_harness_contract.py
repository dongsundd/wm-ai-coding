import re
import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = PLUGIN_ROOT / "skills"


def skill_text(name: str) -> str:
    return (SKILLS_ROOT / name / "SKILL.md").read_text(encoding="utf-8")


def description(body: str) -> str:
    match = re.search(r"(?m)^description:\s*(.+)$", body)
    if not match:
        raise AssertionError("missing skill description")
    return match.group(1).strip().strip('"')


class HarnessContractTest(unittest.TestCase):
    INTERNAL_SUPPORT_SKILLS = (
        "analyze-codegraph-impact",
        "brainstorming",
        "frontend-design",
        "harmonyos-ai-coding",
        "python-ai-coding",
        "research-with-playwright",
        "rust-ai-coding",
        "systematic-debugging",
        "test-driven-development",
        "using-git-worktrees",
    )
    REDUNDANT_ORCHESTRATORS = (
        "dispatching-parallel-agents",
        "executing-plans",
        "finishing-a-development-branch",
        "receiving-code-review",
        "requesting-code-review",
        "subagent-driven-development",
        "using-superpowers",
        "verification-before-completion",
        "writing-plans",
        "openspec-explore",
        "openspec-ff-change",
    )

    def test_using_wm_is_the_only_user_facing_workflow_entry(self) -> None:
        self.assertTrue((SKILLS_ROOT / "using-wm" / "SKILL.md").is_file())
        self.assertFalse((SKILLS_ROOT / "run-ai-coding-harness").exists())
        self.assertIn("name: using-wm", skill_text("using-wm"))

    def test_openspec_stage_skills_require_using_wm_handoff(self) -> None:
        for path in sorted(SKILLS_ROOT.glob("openspec-*/SKILL.md")):
            with self.subTest(skill=path.parent.name):
                body = path.read_text(encoding="utf-8")
                self.assertIn("## Harness entry contract", body)
                self.assertIn("`using-wm`", description(body))
                self.assertNotIn("Also use when the user says", description(body))
                self.assertIn("return control to `using-wm`", body)

    def test_supporting_profiles_reference_the_renamed_harness(self) -> None:
        for name in ("harmonyos-ai-coding", "python-ai-coding", "rust-ai-coding"):
            with self.subTest(skill=name):
                body = skill_text(name)
                self.assertIn("`using-wm`", body)
                self.assertNotIn("run-ai-coding-harness", body)

    def test_supporting_skills_are_internal_harness_stages(self) -> None:
        for name in self.INTERNAL_SUPPORT_SKILLS:
            with self.subTest(skill=name):
                body = skill_text(name)
                self.assertIn("## Harness entry contract", body)
                self.assertIn("`using-wm`", description(body))
                self.assertIn("return control to `using-wm`", body)

    def test_redundant_superpowers_orchestrators_are_removed(self) -> None:
        existing = [name for name in self.REDUNDANT_ORCHESTRATORS if (SKILLS_ROOT / name).exists()]
        self.assertEqual([], existing)

    def test_harness_owns_one_tasks_file_and_minimum_task_contract(self) -> None:
        body = skill_text("using-wm")
        self.assertIn("`tasks.md` is the only implementation plan", body)
        self.assertIn("minimum independently acceptable loop", body)
        self.assertNotIn("Run `writing-plans`", body)
        self.assertNotIn("Use `executing-plans`", body)

    def test_design_artifact_writers_preserve_owned_frontend_section(self) -> None:
        required = "Preserve `## Frontend design` byte-for-byte"
        for name in ("openspec-propose", "openspec-continue-change", "openspec-update-change"):
            with self.subTest(skill=name):
                self.assertIn(required, skill_text(name))

        harness = skill_text("using-wm")
        frontend = skill_text("frontend-design")
        self.assertIn("OpenSpec writes the design skeleton first", harness)
        self.assertIn("only writer for `## Frontend design`", frontend)
        self.assertIn("never replace the whole `design.md` file", frontend)

    def test_old_harness_name_is_absent_from_plugin(self) -> None:
        offenders = []
        for path in PLUGIN_ROOT.rglob("*"):
            if path.is_file() and path.suffix in {".md", ".py", ".json", ".yaml"}:
                if path != Path(__file__) and "run-ai-coding-harness" in path.read_text(encoding="utf-8"):
                    offenders.append(str(path.relative_to(PLUGIN_ROOT)))
        self.assertEqual([], offenders)


if __name__ == "__main__":
    unittest.main()
