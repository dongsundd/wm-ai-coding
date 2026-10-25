from __future__ import annotations

import re
from uuid import uuid4

from wm_ai_coding.evidence.inspection import inspect_change, tree_digest, digest, has_content
from wm_ai_coding.evidence.runs import verification_findings, task_acceptance, workspace_files, inputs
from wm_ai_coding.infrastructure.registry import role_for, canonical_skill
from wm_ai_coding.evidence.reviews import review_findings
from wm_ai_coding.infrastructure.identity import fingerprint


from .common import MachineError, now

class HandoffOperations:
    def _required_support(self, item: dict) -> list[str]:
        skills = list(self.workflow.states[item["stage"]].required_skills)
        if item["stage"] == "specify" and item.get("conditions", {}).get("frontend_surface_changed") is True:
            position = skills.index("test-design") if "test-design" in skills else len(skills)
            skills.insert(position, "frontend-design")
        return skills


    def _support_fingerprint(self, item: dict, skill: str) -> str:
        path = self._change_path(item["name"])
        if skill == "technical-design":
            body = (path / "design.md").read_text(encoding="utf-8") if (path / "design.md").is_file() else ""
            # The conditional frontend writer owns this section after structural design.
            body = re.sub(r"(?ms)^## Frontend design\s*\n.*?(?=^## |\Z)", "", body).strip()
            return fingerprint({"proposal": digest(path / "proposal.md"),
                                "specs": tree_digest(path / "specs"), "design": body})
        if skill == "frontend-design":
            body = (path / "design.md").read_text(encoding="utf-8")
            section = re.search(r"(?ms)^## Frontend design\s*\n.*?(?=^## |\Z)", body)
            return fingerprint({"technical": self._support_fingerprint(item, "technical-design"),
                                "frontend": section.group(0).strip() if section else None})
        if skill in {"test-execution", "code-review"}:
            value = inputs(self.repo, path)
            if skill == "code-review":
                value["review"] = digest(path / "review.json")
            return fingerprint(value)
        return inspect_change(path)["planning_digest"]


    def _require_support(self, item: dict, parent: dict, *, before: str | None = None) -> None:
        required = self._required_support(item)
        if before is not None:
            required = required[:required.index(before)]
        for skill in required:
            records = [h for h in item.get("handoff_history", [])
                       if h.get("parent_id") == parent["id"] and h.get("skill") == skill
                       and h.get("status") == "completed"]
            if not records or records[-1].get("support_fingerprint") != self._support_fingerprint(item, skill):
                raise MachineError(f"required support missing or stale: {skill}")


    def handoff(self, change: str | None, *, scope: list[str], skill: str | None = None, parent_id: str | None = None) -> dict:
        state = self._read()
        name = self._select_change(state, change)
        item = state["changes"][name]
        if item["status"] != "ready":
            raise MachineError("handoff requires a ready change")
        if not scope:
            raise MachineError("handoff needs an explicit scope")
        for path in scope:
            self._scoped_path(path)
        previous = item.get("last_handoff")
        if previous and previous["status"] == "running" and parent_id != previous["id"]:
            raise MachineError("handoff already running")
        if parent_id and (not previous or previous["id"] != parent_id or previous["status"] != "running"):
            raise MachineError("parent handoff is missing or stale")
        if parent_id:
            for path in scope:
                if not any(self._scoped_path(path).is_relative_to(self._scoped_path(p)) for p in previous["scope"]):
                    raise MachineError("child scope cannot expand parent scope")
        evidence = inspect_change(self._change_path(name))
        missing = self._missing_gates(item, evidence, include_exit=False)
        if missing:
            raise MachineError("missing gates: " + ", ".join(missing))
        current = self.workflow.states[item["stage"]]
        allowed = [current.skill] + [conditional.skill for conditional in current.conditional_skills
                                   if item.get("conditions", {}).get(conditional.when) is True]
        selected = canonical_skill(self.workflow, skill or current.skill, item["stage"])
        role = role_for(self.workflow, selected, item["stage"])
        conditional = {c.skill: c.when for c in current.conditional_skills}
        if selected in conditional and item.get("conditions", {}).get(conditional[selected]) is not True:
            raise MachineError("conditional skill is not enabled for this stage")
        if selected not in allowed and role not in {"support", "profile", "operation"}:
            raise MachineError("skill is not enabled for this stage")
        if role in {"support", "profile"} and not parent_id:
            raise MachineError("support/profile needs an active parent handoff")
        if parent_id and role not in {"support", "profile"}:
            raise MachineError("only support/profile may nest inside a stage")
        if selected in self._required_support(item):
            if not previous or previous.get("skill") != current.skill or previous.get("kind") != "stage":
                raise MachineError("required support needs the active primary stage parent")
            self._require_support(item, previous, before=selected)
        handoff = {"id": uuid4().hex, "controller": "development-workflow", "change": name,
                   "stage": item["stage"], "skill": selected, "requested_skill": skill or current.skill, "task": item.get("current_task"),
                   "scope": scope, "inputs": evidence, "status": "running", "started_at": now(),
                   "instruction": "Perform only this scope and return control to development-workflow."}
        handoff.update(kind=role, parent_id=parent_id, trace_id=uuid4().hex,
                       workspace_id=str(self.repo), files_before=workspace_files(self.repo, process=True))
        if role == "stage" and selected == current.skill:
            handoff["required_skills"] = self._required_support(item)
        if parent_id:
            item.setdefault("handoff_stack", []).append(previous)
        item["last_handoff"] = handoff
        self._write(state, state["revision"], "handoff_started")
        return handoff


    def finish_handoff(self, change: str | None, handoff_id: str, result: str, outputs: list[str], *, reason: str = "") -> dict:
        state = self._read()
        name = self._select_change(state, change)
        item = state["changes"][name]
        handoff = item.get("last_handoff")
        if (not handoff or handoff["id"] != handoff_id or handoff["status"] != "running"
                or handoff["stage"] != item["stage"] or handoff.get("task") != item.get("current_task")):
            raise MachineError("handoff is missing, stale or already settled")
        if result not in {"completed", "blocked", "scope_changed", "failed"}:
            raise MachineError("invalid handoff result")
        if result == "completed" and not outputs:
            raise MachineError("completed handoff requires output paths")
        for path in outputs:
            output = self._scoped_path(path)
            if not output.is_file():
                raise MachineError(f"handoff output is missing: {path}")
            if not any(output == self._scoped_path(scope) or output.is_relative_to(self._scoped_path(scope))
                       for scope in handoff["scope"]):
                raise MachineError(f"handoff output is outside scope: {path}")
        if result == "completed":
            evidence = inspect_change(self._change_path(name))
            missing = self._missing_gates(item, evidence, include_exit=False)
            if missing:
                raise MachineError("handoff missing gates: " + ", ".join(missing))
            if handoff["skill"] == "frontend-design" and not evidence["frontend_design"]:
                raise MachineError("frontend design handoff is incomplete")
            if handoff.get("skill") == "technical-design" and not all(evidence[k] for k in ("design", "structural_analysis", "specs")):
                raise MachineError("technical design artifacts are incomplete")
            if handoff.get("skill") == "test-design" and not has_content(self._change_path(name) / "test-design.md"):
                raise MachineError("test-design.md is missing or empty")
            if handoff.get("skill") == "test-execution" and item["stage"] == "verify":
                if findings := verification_findings(self.repo, self._change_path(name)):
                    raise MachineError("test execution evidence: " + "; ".join(findings))
            if handoff.get("skill") == "code-review":
                if findings := review_findings(self.repo, self._change_path(name), item["conditions"].get("frontend_surface_changed") is True):
                    raise MachineError("code review evidence: " + "; ".join(findings))
            if handoff.get("skill") in self._required_support(item):
                parent = item["handoff_stack"][-1]
                self._require_support(item, parent, before=handoff["skill"])
                handoff["support_fingerprint"] = self._support_fingerprint(item, handoff["skill"])
            elif handoff.get("kind") == "stage" and handoff["skill"] == self.workflow.states[item["stage"]].skill:
                self._require_support(item, handoff)
            if handoff.get("kind") in {"support", "profile"}:
                pass
            elif handoff.get("kind") == "operation":
                pass  # Operations cannot create task receipts or replace the primary stage.
            elif item["stage"] == "apply":
                task = next((task for task in evidence["task_states"]
                             if item.get("current_task") and task["title"] == item["current_task"]["title"]), None)
                if not task or not task["complete"] or not evidence["task_contract_valid"]:
                    raise MachineError("handoff task acceptance is incomplete")
                try:
                    records = task_acceptance(self.repo, self._change_path(name), task, handoff_id=handoff["id"])
                except ValueError as exc:
                    raise MachineError(str(exc)) from exc
                item.setdefault("task_receipts", {})[task["id"]] = {
                    "planning": evidence["planning_digest"], "tasks": evidence["tasks_digest"],
                    "handoff_id": handoff["id"], "runs": records, "completed_at": now()}
            else:
                required = {"clarify": ["design"], "specify": ["proposal", "specs", "design", "structural_analysis"],
                            "tasks": ["task_contract_valid"], "verify": ["verification"]}.get(item["stage"], [])
                if any(not evidence[key] for key in required):
                    raise MachineError("handoff stage artifacts are incomplete")
                if item["stage"] in {"verify", "close"}:
                    missing = self._missing_gates(item, evidence)
                    if missing:
                        raise MachineError("handoff missing gates: " + ", ".join(missing))
        if result == "completed":
            before = handoff.get("files_before")
            if before is None:
                raise MachineError("legacy handoff has no write inventory; fail and retry")
            after = workspace_files(self.repo, process=True)
            changed = [p for p in before.keys() | after.keys() if before.get(p) != after.get(p)]
            outside = [p for p in changed if not any(self._scoped_path(p).is_relative_to(self._scoped_path(s)) for s in handoff["scope"])]
            if outside:
                raise MachineError("actual writes outside scope: " + ", ".join(outside[:10]))
            handoff["changed_files"] = changed
        if result != "completed" and not reason.strip():
            raise MachineError("unsuccessful handoff requires a reason")
        handoff.update(status=result, outputs=outputs, reason=reason, finished_at=now())
        item.setdefault("handoff_history", []).append({k:v for k,v in handoff.items() if k != "files_before"})
        if handoff.get("parent_id"):
            item["last_handoff"] = item["handoff_stack"].pop()
        if result != "completed":
            item["status"] = "blocked"
            item["blocker"] = {"reason": reason, "recorded_at": now()}
        return self._write(state, state["revision"], "handoff_finished")


