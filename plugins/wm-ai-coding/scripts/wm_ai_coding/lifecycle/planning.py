from __future__ import annotations


from wm_ai_coding.evidence.inspection import inspect_change, tree_digest, has_content
from wm_ai_coding.evidence.runs import load_plan
from wm_ai_coding.lifecycle.specs import read_tree, validate_sync


from .common import MachineError, now

class PlanningOperations:
    def approve_design(self, change: str | None = None, *, reference: str | None = None) -> dict:
        state = self._read()
        revision = state["revision"]
        name = self._select_change(state, change)
        evidence = inspect_change(self.repo / "sdd" / "changes" / name)
        if not evidence["design"] or not evidence["design_digest"]:
            raise MachineError("design.md is missing or empty")
        if not reference or not reference.strip():
            raise MachineError("approval requires an explicit authorization reference")
        item = state["changes"][name]
        if item["stage"] != "specify":
            raise MachineError("design approval is only valid during specify")
        if not self._gate("frontend_design", item, evidence):
            raise MachineError("frontend applicability or frontend design is incomplete")
        state["changes"][name]["approvals"]["design"] = {
            "status": "approved", "source": "operator_reference", "reference": reference.strip(),
            "artifact_sha256": evidence["design_digest"], "planning_sha256": evidence["planning_digest"],
            "frontend_surface_changed": item["conditions"]["frontend_surface_changed"], "approved_at": now()
        }
        return self._write(state, revision, "design_approved")


    def baseline_tasks(self, change: str | None = None) -> dict:
        state = self._read()
        revision = state["revision"]
        name = self._select_change(state, change)
        evidence = inspect_change(self.repo / "sdd" / "changes" / name)
        item = state["changes"][name]
        if item["stage"] != "tasks":
            raise MachineError("tasks can only be baselined during tasks")
        missing = self._missing_gates(item, evidence, include_exit=False)
        if missing:
            raise MachineError("missing gates: " + ", ".join(missing))
        if not evidence["task_contract_valid"] or any(not t.get("checks") for t in evidence["task_states"]):
            raise MachineError("tasks.md does not satisfy the task contract; each task needs - Check: identifiers")
        if ("test-design" in self.workflow.states["specify"].required_skills
                and not has_content(self._change_path(name) / "test-design.md")):
            raise MachineError("test-design.md is missing; rewind to specify and complete test design before baselining")
        try:
            checks = load_plan(self._change_path(name))
            for task in evidence["task_states"]:
                for check_id in task["checks"]:
                    if not any(c["id"] == check_id and c.get("task") == task["id"] for c in checks):
                        raise ValueError(f"task check mapping missing: {task['id']} / {check_id}")
        except ValueError as exc:
            raise MachineError(str(exc)) from exc
        state["changes"][name]["baselines"]["tasks"] = {
            "status": "current", "artifact_sha256": evidence["tasks_digest"],
            "planning_sha256": evidence["planning_digest"], "recorded_at": now()
        }
        return self._write(state, revision, "tasks_baselined")


    def baseline_specs(self, change: str | None = None) -> dict:
        state = self._read()
        revision = state["revision"]
        name = self._select_change(state, change)
        if state["changes"][name]["stage"] != "close":
            raise MachineError("specs can only be marked synced during close")
        missing = self._missing_gates(state["changes"][name], inspect_change(self._change_path(name)), include_exit=False)
        if missing:
            raise MachineError("missing gates: " + ", ".join(missing))
        item = state["changes"][name]
        before = item.get("spec_preimage")
        if before is None:
            raise MachineError("spec synchronization needs a captured preimage")
        findings = validate_sync(before, read_tree(self._change_path(name) / "specs"), read_tree(self.repo / "sdd/specs"))
        if findings:
            raise MachineError("; ".join(findings))
        specs_digest = tree_digest(self.repo / "sdd" / "specs")
        if not specs_digest:
            raise MachineError("sdd/specs has no durable specifications")
        state["changes"][name]["baselines"]["specs"] = {
            "status": "synced",
            "artifact_sha256": specs_digest,
            "recorded_at": now(),
        }
        return self._write(state, revision, "specs_synced")


