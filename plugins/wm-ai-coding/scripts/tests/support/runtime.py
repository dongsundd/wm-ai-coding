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


TASKS_TEMPLATE = """# Tasks

### Task {index}: {title}

- [ ] Requirement: R{index}
- [ ] Outcome: O{index}
- [ ] Files: file{index}.py
- [ ] Interfaces: none
- [ ] Acceptance: A{index}
- [ ] Verification: python -c "pass"
- Check: task-{index}
"""


def write_change(repo: Path, name: str = "c1", task_count: int = 2) -> Path:
    change = repo / "sdd" / "changes" / name
    (change / "specs" / "capability").mkdir(parents=True)
    (change / "proposal.md").write_text("# Proposal\n\nDo the work.\n", encoding="utf-8")
    (change / "specs" / "capability" / "spec.md").write_text("## ADDED Requirements\n### Requirement: R1\nWorks.\n#### Scenario: success\nWorks.\n", encoding="utf-8")
    (change / "design.md").write_text(
        "# Design\n\nUse the existing path.\n\n"
        "## Structural analysis\n\n"
        "- Source: CodeGraph\n"
        "- Entry points: existing.path\n"
        "- Impact: bounded to the existing path\n",
        encoding="utf-8",
    )
    (change / "test-design.md").write_text(
        "# Test design\n\nR1 / success: exercise accepted behavior; expect success.\n", encoding="utf-8")
    tasks = "# Tasks\n\n" + "".join(
        TASKS_TEMPLATE.format(index=index, title=f"Deliver outcome {index}")
        for index in range(1, task_count + 1)
    )
    (change / "tasks.md").write_text(tasks, encoding="utf-8")
    (change / "verification-plan.json").write_text(json.dumps({"checks": [
        {"id": f"task-{i}", "task": f"task-{i}", "kind": "test", "argv": [sys.executable, "-c", "print('accepted')"],
         "requirements": ["capability::R1"], "scenarios": ["capability::R1::success"]}
        for i in range(1, task_count+1)]}), encoding="utf-8")
    return change


def complete_task(tasks_path: Path, index: int, task_count: int = 2) -> None:
    lines = tasks_path.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(f"### Task {index}:"))
    end = len(lines)
    for candidate in range(start + 1, len(lines)):
        if lines[candidate].startswith("### Task "):
            end = candidate
            break
    for line_index in range(start, end):
        lines[line_index] = lines[line_index].replace("- [ ]", "- [x]")
    tasks_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def machine_for(repo: Path) -> StateMachine:
    return StateMachine(repo, load_workflow(PLUGIN_ROOT / "skills" / "development-workflow" / "config" / "workflow.yaml"))


def advance_stage(machine):
    packet=machine.recovery()
    handoff=packet.get("handoff")
    if not handoff or handoff.get("status") != "running" or handoff.get("stage") != packet["stage"]:
        handoff=machine.handoff(None,scope=["sdd"])
    complete_supports(machine, handoff)
    machine.finish_handoff(None,handoff["id"],"completed",[f"sdd/changes/{packet['change']}/design.md"])
    return machine.advance()


def complete_supports(machine, handoff):
    """Fixtures perform real child handoffs rather than bypassing support evidence."""
    packet = machine.recovery()
    steps = {'specify': [('technical-design', 'design.md'), ('test-design', 'test-design.md')],
             'verify': [('test-execution', 'verification.md'), ('code-review', 'review.json')]}.get(packet['stage'], [])
    if packet['stage'] == 'specify' and packet['conditions'].get('frontend_surface_changed') is True:
        steps.insert(1, ('frontend-design', 'design.md'))
    for skill, output in steps:
        child = machine.handoff(None, scope=handoff['scope'], skill=skill, parent_id=handoff['id'])
        machine.finish_handoff(None, child['id'], 'completed', [f"sdd/changes/{packet['change']}/{output}"])


def accept_task(machine, change, index):
    handoff=machine.recovery().get("handoff")
    if not handoff or handoff.get("status") != "running":
        handoff=machine.handoff(None,scope=["sdd"])
    machine.run_check(None,f"task-{index}")
    complete_task(change/"tasks.md",index)
    machine.finish_handoff(None,handoff["id"],"completed",[f"sdd/changes/{change.name}/tasks.md"])


def advance_to_apply(repo: Path, frontend_text: str = "") -> tuple[StateMachine, Path]:
    machine=machine_for(repo);change=write_change(repo)
    if frontend_text:
        with (change/'design.md').open('a',encoding='utf-8') as handle:
            handle.write('\n## Frontend design\n'+frontend_text+'\n')
    machine.init(gitignore=False)
    advance_stage(machine)
    machine.set_frontend(None,False);machine.approve_design(reference="test:user-request")
    advance_stage(machine)
    machine.baseline_tasks();advance_stage(machine)
    return machine,change


