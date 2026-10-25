from __future__ import annotations
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from support.runtime import advance_to_apply, complete_task, machine_for, write_change, advance_stage, accept_task, complete_supports
from wm_ai_coding.lifecycle.machine import MachineError


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
    from wm_ai_coding.evidence.reviews import record_review
    record_review(repo,change,reviewer="fixture-review",mode="self",findings=[])
    (change/"verification.json").write_text(json.dumps({"schema_version":1,"status":"passed","coverage":{
        "capability::R1":[record["id"]],"capability::R1::success":[record["id"]]}}))
    complete_supports(machine,handoff)
    machine.finish_handoff(None,handoff["id"],"completed",["sdd/changes/c1/verification.md"])
    return machine,change

