from __future__ import annotations

import subprocess
import re
from pathlib import Path

from wm_ai_coding.evidence.inspection import inspect_change, ready_tasks, tree_digest, digest
from wm_ai_coding.infrastructure.store import StateStore
from wm_ai_coding.infrastructure.workflow import Workflow
from wm_ai_coding.evidence.runs import run_check, verification_findings, load_plan
from wm_ai_coding.lifecycle.archives import integrity_for
from wm_ai_coding.lifecycle.specs import read_tree
from wm_ai_coding.evidence.reviews import review_findings, verification_summary
from wm_ai_coding.infrastructure.identity import PROTOCOL_VERSION


from .common import MachineError, STAGE_ALIASES, GITIGNORE_BEGIN, GITIGNORE_END, MANAGED_GITIGNORE_BLOCK, now

from .planning import PlanningOperations
from .handoffs import HandoffOperations
from .closure import ClosureOperations


class StateMachine(PlanningOperations, HandoffOperations, ClosureOperations):
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
                from wm_ai_coding.evidence.inspection import digest
                if record.get("stdout_sha256") != digest(directory / "stdout.log") or record.get("stderr_sha256") != digest(directory / "stderr.log"):
                    return False
            if not receipt.get("runs"):
                return False
        return True



    def batch_checks(self, change: str | None, jobs: list[dict], *, max_parallel: int = 2) -> dict:
        from wm_ai_coding.evidence.batch import run_batch
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
