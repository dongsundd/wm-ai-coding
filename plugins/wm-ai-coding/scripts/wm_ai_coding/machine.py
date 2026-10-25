from __future__ import annotations

import subprocess
import json
import re
from uuid import uuid4
from datetime import datetime, timezone
from pathlib import Path

from .evidence import artifact_tree_digest, inspect_change, ready_tasks, tree_digest, digest, has_content
from .store import StateStore
from .workflow import Workflow
from .runs import run_check, verification_findings, task_acceptance, workspace_files, inputs, load_plan
from .registry import role_for, canonical_skill
from .archives import integrity_for, export_evidence, write_manifest
from .specs import read_tree, expected_specs, validate_sync
from .reviews import review_findings, verification_summary
from .identity import PROTOCOL_VERSION, fingerprint


class MachineError(RuntimeError):
    pass


STAGE_ALIASES = {"impact": "specify"}
GITIGNORE_BEGIN = "# BEGIN WM AI CODING"
GITIGNORE_END = "# END WM AI CODING"
MANAGED_GITIGNORE_BLOCK = """# BEGIN WM AI CODING
.wm/

# Keep only durable archived SDD artifacts in version control.
/sdd/changes/*
!/sdd/changes/archive/
!/sdd/changes/archive/**/
!/sdd/changes/archive/**/*
# END WM AI CODING
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class StateMachine:
    def __init__(self, repo: Path, workflow: Workflow):
        self.repo = repo.resolve()
        self.workflow = workflow
        self.store = StateStore(self.repo)

    def _change_dirs(self) -> list[Path]:
        root = self.repo / "sdd" / "changes"
        if not root.is_dir():
            return []
        return sorted(path for path in root.iterdir() if path.is_dir() and path.name != "archive")

    def _change_path(self, name: str) -> Path:
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name) or name == "archive":
            raise MachineError("invalid change name")
        root = (self.repo / "sdd" / "changes").resolve()
        if not root.is_relative_to(self.repo):
            raise MachineError("process root escapes the repository")
        path = root / name
        if path.resolve().parent != root:
            raise MachineError("change path escapes its root")
        return path

    def _scoped_path(self, value: str) -> Path:
        path = (self.repo / value).resolve()
        if not value.strip() or not path.is_relative_to(self.repo):
            raise MachineError("path must stay inside the repository")
        return path

    def _new_change(self, name: str) -> dict:
        return {
            "name": name,
            "protocol_version": PROTOCOL_VERSION,
            "task_receipts": {},
            "handoff_stack": [],
            "stage": self.workflow.initial,
            "status": "ready",
            "current_task": None,
            "completed_stages": [],
            "approvals": {},
            "baselines": {},
            "blocker": None,
            "last_handoff": None,
            "conditions": {"frontend_surface_changed": None},
            "evidence_snapshot": inspect_change(self._change_path(name)),
            "last_valid_stage": self.workflow.initial,
            "required_stage": None,
        }

    def _ensure_gitignore(self) -> bool:
        path = self.repo / ".gitignore"
        existing = path.read_text(encoding="utf-8") if path.is_file() else ""
        existing = existing.replace("\r\n", "\n").replace("\r", "\n")
        if MANAGED_GITIGNORE_BLOCK in existing:
            return False
        begin = existing.find(GITIGNORE_BEGIN)
        end = existing.find(GITIGNORE_END, begin + len(GITIGNORE_BEGIN)) if begin >= 0 else -1
        if begin >= 0 and end >= 0:
            suffix_start = end + len(GITIGNORE_END)
            if suffix_start < len(existing) and existing[suffix_start] == "\n":
                suffix_start += 1
            updated = existing[:begin] + MANAGED_GITIGNORE_BLOCK + existing[suffix_start:]
        elif begin >= 0:
            updated = existing[:begin] + MANAGED_GITIGNORE_BLOCK
        else:
            separator = "" if not existing or existing.endswith("\n") else "\n"
            updated = existing + separator + MANAGED_GITIGNORE_BLOCK
        path.write_text(updated, encoding="utf-8", newline="\n")
        return True

    def _untrack_ignored_sdd_files(self) -> list[str]:
        try:
            result = subprocess.run(
                ["git", "-C", str(self.repo), "ls-files", "-z", "--", "sdd/changes"],
                capture_output=True,
                check=False,
                timeout=10,
            )
        except FileNotFoundError:
            return []
        except subprocess.TimeoutExpired as exc:
            raise MachineError("timed out while inspecting the Git index") from exc
        if result.returncode != 0:
            return []
        tracked = (path for path in result.stdout.decode("utf-8").split("\0") if path)
        paths = []
        for path in tracked:
            parts = Path(path).as_posix().split("/")
            active_change = len(parts) >= 3 and parts[:2] == ["sdd", "changes"] and parts[2] != "archive"
            archived_record = (
                len(parts) >= 4
                and parts[:3] == ["sdd", "changes", "archive"]
                and parts[-1] in {"tasks.md", "verification.md"}
            )
            if active_change:
                paths.append(path)
        paths.sort()
        if not paths:
            return []
        try:
            removed = subprocess.run(
                ["git", "-C", str(self.repo), "rm", "-q", "-f", "--cached", "--ignore-unmatch", "--", *paths],
                capture_output=True,
                check=False,
                text=True,
                timeout=30,
            )
        except subprocess.TimeoutExpired as exc:
            raise MachineError("timed out while removing ignored SDD files from the Git index") from exc
        if removed.returncode != 0:
            detail = removed.stderr.strip() or removed.stdout.strip() or "unknown Git error"
            raise MachineError(f"failed to remove ignored SDD files from the Git index: {detail}")
        return paths

    def init(self, *, gitignore: bool = True) -> dict:
        maintenance = {"gitignore_changed": False, "untracked_files": []}
        if gitignore:
            maintenance["gitignore_changed"] = self._ensure_gitignore()
            maintenance["untracked_files"] = self._untrack_ignored_sdd_files()
        if self.store.path.exists():
            state = self.store.read()
            if state.get("workflow", {}).get("checksum") != self.workflow.checksum:
                raise MachineError("workflow checksum changed; run wm migrate")
            state["maintenance"] = maintenance
            return state
        names = [path.name for path in self._change_dirs()]
        state = {
            "schema_version": 1,
            "workflow": {"name": self.workflow.name, "version": self.workflow.schema_version, "checksum": self.workflow.checksum},
            "revision": 0,
            "active_change": names[0] if len(names) == 1 else None,
            "changes": {name: self._new_change(name) for name in names},
            "updated_at": now(),
        }
        self.store.directory.mkdir(parents=True, exist_ok=True)
        for name in ("runs", "recovery", "tmp"):
            (self.store.directory / name).mkdir(exist_ok=True)
        state = self.store.write(state, expected_revision=0, event="initialized")
        state["maintenance"] = maintenance
        return state

    def _read(self) -> dict:
        state = self.store.read()
        workflow = state.get("workflow", {})
        if workflow.get("checksum") != self.workflow.checksum:
            raise MachineError("workflow checksum changed; run wm migrate")
        for name, item in state.get("changes", {}).items():
            item["name"] = name
            item.setdefault("conditions", {"frontend_surface_changed": None})
        return state

    def _state_order(self) -> list[str]:
        order: list[str] = []
        name: str | None = self.workflow.initial
        while name is not None and name not in order:
            order.append(name)
            state = self.workflow.states.get(name)
            name = state.next if state else None
        return order

    def _rewind_for_drift(self, item: dict, target: str) -> None:
        order = self._state_order()
        if target in order and item.get("stage") in order:
            target_index = order.index(target)
            if target_index < order.index(item["stage"]):
                item["stage"] = target
                item["completed_stages"] = order[:target_index]
                item["current_task"] = None
        if item["status"] != "blocked":
            item["status"] = "ready"
        item["required_stage"] = target

    def _select_change(self, state: dict, change: str | None) -> str:
        name = change or state.get("active_change")
        if not name or name not in state["changes"]:
            raise MachineError("select an active change")
        self._change_path(name)
        return name

    def status(self, change: str | None = None) -> dict:
        state = self._read()
        if change:
            self._select_change(state, change)
        # Read-only projection: expose live evidence without silently writing state.
        for name, item in state["changes"].items():
            if item["status"] == "archived":
                item["integrity"] = integrity_for(self.repo, item)
                continue
            path = self._change_path(name)
            if item.get("archive_intent") and not path.exists():
                continue
            evidence = inspect_change(path)
            item["live_evidence"] = evidence
            item["missing_gates"] = self._missing_gates(item, evidence)
        return state

    def migrate(self) -> dict:
        state = self.store.read()
        if state.get("workflow", {}).get("checksum") == self.workflow.checksum:
            return state
        unmapped: list[str] = []
        for name, item in state.get("changes", {}).items():
            if item.get("status") == "archived":
                continue  # Historical diagnostics are immutable across runtime migrations.
            stage = item.get("stage")
            if stage not in self.workflow.states:
                target = STAGE_ALIASES.get(stage)
                if target not in self.workflow.states:
                    unmapped.append(f"{name}: {stage}")
                    continue
                item["stage"] = target
            if item.get("last_valid_stage") not in self.workflow.states:
                item["last_valid_stage"] = item["stage"]
            if item.get("required_stage") not in self.workflow.states:
                item["required_stage"] = None
            if item.get("status") != "archived":
                item["current_task"] = None
                item["protocol_version"] = PROTOCOL_VERSION
                item["task_receipts"] = {}
                item["handoff_stack"] = []
                item["last_handoff"] = None
                if self._state_order().index(item["stage"]) >= self._state_order().index("apply"):
                    item["stage"] = "tasks"
                    item["baselines"].pop("tasks", None)
                    item["completed_stages"] = ["clarify", "specify"]
            item["evidence_snapshot"] = inspect_change(self.repo / "sdd" / "changes" / name)
        if unmapped:
            raise MachineError("cannot migrate unknown workflow stages: " + ", ".join(unmapped))
        state["workflow"] = {
            "name": self.workflow.name,
            "version": self.workflow.schema_version,
            "checksum": self.workflow.checksum,
        }
        return self.store.write(state, expected_revision=state["revision"], event="workflow_migrated")

    def _write(self, state: dict, original_revision: int, event: str) -> dict:
        state["updated_at"] = now()
        return self.store.write(state, expected_revision=original_revision, event=event)

    def select(self, change: str) -> dict:
        state = self._read()
        if change not in state["changes"]:
            raise MachineError(f"unknown change: {change}")
        if state["changes"][change]["status"] == "archived":
            raise MachineError("cannot select an archived change for execution")
        revision = state["revision"]
        state["active_change"] = change
        return self._write(state, revision, "change_selected")

    def reconcile(self, change: str | None = None) -> dict:
        state = self._read()
        revision = state["revision"]
        names = [change] if change else [path.name for path in self._change_dirs()]
        changed = False
        for name in names:
            path = self._change_path(name)
            saved = state["changes"].get(name, {})
            if saved.get("status") == "archived" or (saved.get("archive_intent") and not path.exists()):
                continue
            if not path.is_dir():
                raise MachineError(f"missing change directory: {name}")
            if name not in state["changes"]:
                state["changes"][name] = self._new_change(name)
                changed = True
                continue
            item = state["changes"][name]
            if item["status"] == "archived":
                continue
            evidence = inspect_change(self.repo / "sdd" / "changes" / name)
            approval = item.get("approvals", {}).get("design")
            baseline = item.get("baselines", {}).get("tasks")
            drifted = False
            if approval and approval.get("planning_sha256") != evidence["planning_digest"]:
                approval["status"] = "stale"
                drifted = True
            if baseline and (baseline.get("artifact_sha256") != evidence["tasks_digest"]
                             or baseline.get("planning_sha256") != evidence["planning_digest"]):
                baseline["status"] = "stale"
                drifted = True
            if drifted:
                target = "specify" if approval and approval.get("status") == "stale" else "tasks"
                self._rewind_for_drift(item, target)
            if item.get("evidence_snapshot") != evidence:
                item["evidence_snapshot"] = evidence
                changed = True
            changed = changed or drifted
        return self._write(state, revision, "reconciled") if changed else state

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

    def _gate(self, gate: str, item: dict, evidence: dict) -> bool:
        approval = item.get("approvals", {}).get("design", {})
        baseline = item.get("baselines", {}).get("tasks", {})
        if gate == "verification":
            return evidence["verification"] and not verification_findings(
                self.repo, self._evidence_path(item), change_name=item["name"]) and not review_findings(
                    self.repo, self._evidence_path(item), item.get("conditions", {}).get("frontend_surface_changed") is True, change_name=item["name"]
                ) and not verification_summary(self.repo, self._evidence_path(item), change_name=item["name"])
        return {
            "design_approved": approval.get("status") == "approved"
            and bool(approval.get("reference"))
            and approval.get("planning_sha256") == evidence["planning_digest"]
            and approval.get("frontend_surface_changed") == item.get("conditions", {}).get("frontend_surface_changed"),
            "planning_artifacts": evidence["proposal"] and evidence["specs"] and evidence["design"],
            "structural_analysis": evidence["structural_analysis"],
            "frontend_design": item.get("conditions", {}).get("frontend_surface_changed") is False
            or (item.get("conditions", {}).get("frontend_surface_changed") is True and evidence["frontend_design"]),
            "task_contract": evidence["task_contract_valid"],
            "task_baseline": baseline.get("status") == "current"
            and baseline.get("artifact_sha256") == evidence["tasks_digest"]
            and baseline.get("planning_sha256") == evidence["planning_digest"],
            "all_tasks_complete": evidence["tasks"]
            and evidence["task_contract_valid"]
            and bool(evidence["task_states"])
            and evidence["open_tasks"] == 0 and self._accepted_tasks_valid(item, evidence),
            "specs_synced": item.get("baselines", {}).get("specs", {}).get("status") == "synced"
            and item.get("baselines", {}).get("specs", {}).get("artifact_sha256")
            == tree_digest(self.repo / "sdd" / "specs"),
        }[gate]

    def _evidence_path(self, item: dict) -> Path:
        if item.get("archive_path") and item["status"] == "archived":
            return self._scoped_path(item["archive_path"])
        if item.get("archive_intent") and not self._change_path(item["name"]).exists():
            return self._scoped_path(item["archive_intent"]["target"])
        return self._change_path(item["name"])

    def _missing_gates(self, item: dict, evidence: dict, *, include_exit: bool = True) -> list[str]:
        order = self._state_order()
        index = order.index(item["stage"])
        gates: list[str] = []
        for stage in order[:index + (1 if include_exit else 0)]:
            gates.extend(self.workflow.states[stage].exit_gates)
        return [gate for gate in dict.fromkeys(gates) if not self._gate(gate, item, evidence)]

    @staticmethod
    def _task_ref(task: dict) -> dict:
        return {"index": task["index"], "id": task["id"], "title": task["title"]}

    def _enter_stage(self, item: dict, stage: str, evidence: dict) -> None:
        item["last_handoff"] = None
        item["handoff_stack"] = []
        if stage == "close":
            item["spec_preimage"] = read_tree(self.repo / "sdd/specs")
        if self.workflow.states[stage].repeat == "per_task":
            open_tasks = ready_tasks(evidence["task_states"])
            item["current_task"] = self._task_ref(open_tasks[0]) if open_tasks else None
        else:
            item["current_task"] = None

    def _transition(self, state: dict, revision: int, item: dict, current, evidence: dict) -> dict:
        item["completed_stages"].append(item["stage"])
        item["stage"] = current.next
        item["last_valid_stage"] = current.next
        item["required_stage"] = None
        item["evidence_snapshot"] = evidence
        self._enter_stage(item, current.next, evidence)
        return self._write(state, revision, "advanced")

    def _advance_apply(self, state: dict, revision: int, item: dict, current, evidence: dict) -> dict:
        baseline = item.get("baselines", {}).get("tasks", {})
        if baseline.get("status") != "current" or baseline.get("artifact_sha256") != evidence["tasks_digest"]:
            raise MachineError("tasks.md changed; run wm reconcile and re-baseline tasks")
        open_tasks = [task for task in evidence["task_states"] if not task["complete"]]
        task = item.get("current_task") or {}
        if task.get("id") not in item.get("task_receipts", {}):
            raise MachineError("task acceptance receipt is missing")
        if not open_tasks:
            missing = [gate for gate in current.exit_gates if not self._gate(gate, item, evidence)]
            if missing:
                raise MachineError("missing gates: " + ", ".join(missing))
            return self._transition(state, revision, item, current, evidence)
        open_tasks = ready_tasks(evidence["task_states"])
        if not open_tasks:
            raise MachineError("no task has satisfied dependencies")
        current_task = item.get("current_task")
        if not isinstance(current_task, dict) or not isinstance(current_task.get("title"), str):
            item["current_task"] = self._task_ref(open_tasks[0])
            item["evidence_snapshot"] = evidence
            return self._write(state, revision, "task_selected")
        match = next(
            (task for task in evidence["task_states"] if task["title"] == current_task["title"]),
            None,
        )
        if match is None:
            raise MachineError(f"current task is missing from tasks.md: {current_task['title']}")
        if not match["complete"]:
            raise MachineError(f"current task is not complete: {current_task['title']}")
        item["current_task"] = self._task_ref(open_tasks[0])
        item["last_handoff"] = None
        item["evidence_snapshot"] = evidence
        return self._write(state, revision, "task_advanced")

    def advance(self, change: str | None = None) -> dict:
        state = self._read()
        revision = state["revision"]
        name = self._select_change(state, change)
        item = state["changes"][name]
        if item["status"] in {"blocked", "drifted"}:
            raise MachineError(f"change is {item['status']}")
        current = self.workflow.states[item["stage"]]
        if current.terminal or current.next is None:
            raise MachineError("current stage is terminal")
        evidence = inspect_change(self.repo / "sdd" / "changes" / name)
        handoff = item.get("last_handoff")
        if handoff and handoff["status"] != "completed":
            raise MachineError("handoff has not completed; return or recover it first")
        missing = self._missing_gates(item, evidence, include_exit=False)
        if missing:
            raise MachineError("missing gates: " + ", ".join(missing))
        if current.repeat != "per_task":
            missing = [gate for gate in current.exit_gates if not self._gate(gate, item, evidence)]
            if missing:
                raise MachineError("missing gates: " + ", ".join(missing))
        if (not handoff or handoff.get("stage") != item["stage"] or handoff.get("task") != item.get("current_task")
                or handoff.get("kind") != "stage" or handoff.get("skill") != current.skill):
            raise MachineError("current stage/task needs a completed matching handoff")
        self._require_support(item, handoff)
        if current.repeat == "per_task":
            return self._advance_apply(state, revision, item, current, evidence)
        missing = [gate for gate in current.exit_gates if not self._gate(gate, item, evidence)]
        if missing:
            raise MachineError("missing gates: " + ", ".join(missing))
        return self._transition(state, revision, item, current, evidence)

    def rewind(self, change: str | None, target: str, reason: str) -> dict:
        state = self._read()
        revision = state["revision"]
        name = self._select_change(state, change)
        if target not in self.workflow.states:
            raise MachineError(f"unknown target stage: {target}")
        item = state["changes"][name]
        if item["status"] == "archived" or item.get("archive_intent"):
            raise MachineError("cannot rewind an archived or pending archive change")
        item["stage"] = target
        item["last_valid_stage"] = target
        item["status"] = "ready"
        item["required_stage"] = None
        item["blocker"] = None
        item["current_task"] = None
        item["approvals"] = {}
        item["baselines"] = {}
        item["last_handoff"] = None
        item["handoff_stack"] = []
        item["task_receipts"] = {}
        item.pop("spec_preimage", None)
        item["completed_stages"] = []
        item["rewind_reason"] = reason
        return self._write(state, revision, "rewound")

    def block(self, change: str | None, reason: str) -> dict:
        state = self._read(); revision = state["revision"]; name = self._select_change(state, change)
        if state["changes"][name]["status"] == "archived":
            raise MachineError("cannot block an archived change")
        state["changes"][name]["status"] = "blocked"
        state["changes"][name]["blocker"] = {"reason": reason, "recorded_at": now()}
        return self._write(state, revision, "blocked")

    def resume(self, change: str | None) -> dict:
        state = self._read()
        revision = state["revision"]
        name = self._select_change(state, change)
        if state["changes"][name]["status"] != "blocked":
            raise MachineError("change is not blocked")
        state["changes"][name]["status"] = "ready"
        state["changes"][name]["blocker"] = None
        state["changes"][name]["required_stage"] = None
        return self._write(state, revision, "resumed")

    def set_frontend(self, change: str | None, value: bool) -> dict:
        state = self._read()
        name = self._select_change(state, change)
        item = state["changes"][name]
        if item["stage"] not in {"clarify", "specify"} or item["status"] == "archived":
            raise MachineError("frontend condition can only change during design")
        if type(value) is not bool:
            raise MachineError("frontend condition must be boolean")
        item.setdefault("conditions", {})["frontend_surface_changed"] = value
        if item.get("approvals", {}).get("design"):
            item["approvals"]["design"]["status"] = "stale"
        return self._write(state, state["revision"], "frontend_condition_set")

    def run_check(self, change: str | None, check_id: str, *, timeout: float = 300) -> dict:
        state = self._read()
        name = self._select_change(state, change)
        item = state["changes"][name]
        if item["status"] != "ready" or item["stage"] not in {"apply", "verify", "close", "archive"}:
            raise MachineError("checks require a ready implementation or verification stage")
        try:
            handoff = item.get("last_handoff") or {}
            if handoff.get("parent_id"):
                handoff = item.get("handoff_stack", [handoff])[0]
            context = {"handoff_id": handoff.get("id"), "stage": item["stage"],
                       "parent_trace_id": handoff.get("trace_id")}
            return run_check(self.repo, self._change_path(name), check_id, timeout=timeout, context=context)
        except ValueError as exc:
            raise MachineError(str(exc)) from exc

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

    def recovery(self, change: str | None = None) -> dict:
        state = self._read()
        name = self._select_change(state, change)
        item = state["changes"][name]
        path = self._evidence_path(item)
        if item.get("archive_intent") and not path.exists():
            path = self._scoped_path(item["archive_intent"]["target"])
        evidence = inspect_change(path)
        integrity = integrity_for(self.repo, item) if item["status"] == "archived" else None
        return {"integrity": integrity, "conditions": item.get("conditions", {}), "change": name, "stage": item["stage"], "status": item["status"],
                "task": item.get("current_task"), "handoff": item.get("last_handoff"),
                "blocker": item.get("blocker"), "approvals": item.get("approvals"),
                "baselines": item.get("baselines"), "evidence": evidence,
                "verification_findings": verification_findings(self.repo, path, change_name=name),
                "missing_gates": self._missing_gates(item, evidence) if item["status"] != "archived" else [],
                "next_action": ("archived" if integrity["valid"] else "repair-required") if item["status"] == "archived" else "archive" if item.get("archive_intent") else
                    "resume" if item["status"] == "blocked" else "finish-handoff" if
                    (item.get("last_handoff") or {}).get("status") == "running" else "inspect gates and handoff",
                "artifacts": {name: str(path / name) for name in
                    ("proposal.md", "design.md", "tasks.md", "verification.md", "verification-plan.json")}}

    def archive(self, change: str | None) -> dict:
        state = self._read()
        name = self._select_change(state, change)
        item = state["changes"][name]
        if item["status"] == "archived":
            if not integrity_for(self.repo, item)["valid"]:
                raise MachineError("archived assets failed integrity validation")
            return state
        if item["stage"] != "archive" or item["status"] != "ready":
            raise MachineError("archive requires a ready archive stage")
        handoff = item.get("last_handoff")
        if (not handoff or handoff["status"] not in {"running", "completed"} or handoff["stage"] != "archive"
                or canonical_skill(self.workflow, handoff.get("skill", "")) != "change-archive"):
            raise MachineError("archive requires a completed or current archive handoff")
        source = self._change_path(name)
        intent = item.get("archive_intent")
        if not intent:
            missing = self._missing_gates(item, inspect_change(source))
            if missing:
                raise MachineError("missing gates: " + ", ".join(missing))
            target_name = name if re.match(r"^\d{4}-\d{2}-\d{2}-", name) else f"{now()[:10]}-{name}"
            target = self.repo / "sdd" / "changes" / "archive" / target_name
            self._scoped_path(target.relative_to(self.repo).as_posix())
            if target.exists():
                raise MachineError("archive target already exists")
            if not all(any(path.is_relative_to(self._scoped_path(scope)) for scope in handoff["scope"]) for path in (source, target)):
                raise MachineError("archive source/destination are outside handoff scope")
            export_evidence(self.repo, source, item.get("task_receipts", {}))
            item["archive_manifest_sha256"] = write_manifest(source)
            intent = {"target": target.relative_to(self.repo).as_posix(),
                      "source_digest": artifact_tree_digest(source), "created_at": now()}
            item["archive_intent"] = intent
            state = self._write(state, state["revision"], "archive_started")
            item = state["changes"][name]
        target = self._scoped_path(intent["target"])
        archive_root = (self.repo / "sdd" / "changes" / "archive").resolve()
        if target.parent != archive_root:
            raise MachineError("invalid archive target")
        if source.exists():
            if target.exists():
                raise MachineError("archive source and destination both exist")
            missing = self._missing_gates(item, inspect_change(source))
            if missing or artifact_tree_digest(source) != intent["source_digest"]:
                raise MachineError("archive inputs changed: " + ", ".join(missing))
            target.parent.mkdir(parents=True, exist_ok=True)
            source.rename(target)
        elif not target.is_dir() or artifact_tree_digest(target) != intent["source_digest"]:
            raise MachineError("archive intent cannot be recovered: destination differs")
        # The live gates were checked before the intent and before movement.
        # Declared change-local artifacts now live at target, not their old paths.
        # Recovery validates the pinned portable snapshot rather than replaying
        # live checks against a directory that intentionally no longer exists.
        if artifact_tree_digest(target) != intent["source_digest"]:
            raise MachineError("archive intent cannot be recovered: destination differs")
        handoff = item.get("last_handoff")
        if handoff and handoff["status"] == "running":
            if handoff["stage"] != "archive":
                raise MachineError("unfinished handoff from another stage")
            handoff.update(status="completed", outputs=[intent["target"]], finished_at=now())
        item.update(status="archived", archive_path=intent["target"], archived_at=now(), current_task=None)
        if "archive" not in item["completed_stages"]:
            item["completed_stages"].append("archive")
        if state["active_change"] == name:
            state["active_change"] = None
        return self._write(state, state["revision"], "archived")

    def validate(self) -> dict:
        state = self._read()
        findings: list[str] = []
        gitignore = self.repo / ".gitignore"
        if not gitignore.is_file() or MANAGED_GITIGNORE_BLOCK not in gitignore.read_text(encoding="utf-8"):
            findings.append("WM managed .gitignore policy is missing or incomplete")
        for name in state["changes"]:
            item = state["changes"][name]
            if not self._evidence_path(item).is_dir():
                findings.append(f"missing change directory: {name}")
            elif item["status"] == "archived":
                findings.extend(f"{name}: {finding}" for finding in integrity_for(self.repo, item)["findings"])
        return {"valid": not findings, "findings": findings, "state": state}


    def _accepted_tasks_valid(self, item: dict, evidence: dict) -> bool:
        for task in evidence["task_states"]:
            receipt = item.get("task_receipts", {}).get(task["id"], {})
            if receipt.get("planning") != evidence["planning_digest"] or receipt.get("tasks") != evidence["tasks_digest"]:
                return False
            for record in receipt.get("runs", []):
                directory = self.repo / ".wm/runs" / record["id"]
                from .evidence import digest
                if record.get("stdout_sha256") != digest(directory / "stdout.log") or record.get("stderr_sha256") != digest(directory / "stderr.log"):
                    return False
            if not receipt.get("runs"):
                return False
        return True

    def sync_specs(self, change: str | None = None) -> dict:
        state = self._read(); name = self._select_change(state, change); item = state["changes"][name]
        if item["stage"] != "close" or item["status"] != "ready" or "spec_preimage" not in item:
            raise MachineError("spec sync requires a ready close stage and captured preimage")
        before = item["spec_preimage"]
        current = read_tree(self.repo / "sdd/specs")
        deltas = read_tree(self._change_path(name) / "specs")
        expected = expected_specs(before, deltas)
        # Each path may be the old or expected value after an interrupted multi-file sync.
        for key in current.keys() | before.keys() | expected.keys():
            if current.get(key) not in (before.get(key), expected.get(key)):
                raise MachineError("durable specs drifted from captured preimage")
        if self._missing_gates(item, inspect_change(self._change_path(name)), include_exit=False):
            raise MachineError("verification gates failed before sync")
        root = self.repo / "sdd/specs"; root.mkdir(parents=True, exist_ok=True)
        for key in before.keys() - expected.keys():
            self._scoped_path((root / key).relative_to(self.repo).as_posix()).unlink()
        for key, text in expected.items():
            path = self._scoped_path((root / key).relative_to(self.repo).as_posix())
            path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text, encoding="utf-8")
        return self.baseline_specs(name)


    def batch_checks(self, change: str | None, jobs: list[dict], *, max_parallel: int = 2) -> dict:
        from .batch import run_batch
        state = self._read(); name = self._select_change(state, change); item = state["changes"][name]
        evidence = inspect_change(self._change_path(name))
        if item["status"] != "ready" or item["stage"] != "apply" or self._missing_gates(item, evidence, include_exit=False):
            raise MachineError("batch checks require a ready apply stage with valid planning")
        ready = {task["id"]: task for task in ready_tasks(evidence["task_states"])}
        checks = load_plan(self._change_path(name)); resolved = []
        if not isinstance(jobs, list) or not jobs:
            raise MachineError("batch needs declared jobs")
        for job in jobs:
            if not isinstance(job, dict) or job.get("task") not in ready:
                raise MachineError("unknown or unready batch task")
            check = next((c for c in checks if c["id"] == job.get("check") and c.get("task") == job["task"]), None)
            if check is None or check["id"] not in ready[job["task"]]["checks"]:
                raise MachineError("batch job does not match a declared task check")
            resolved.append({"task": job["task"], "workspace": job.get("workspace"), "argv": check["argv"]})
        result = run_batch(resolved, max_parallel=max_parallel)
        result["change"] = name
        return result
