from __future__ import annotations

import copy
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .evidence import inspect_change
from .store import StateError, StateStore
from .workflow import Workflow


class MachineError(RuntimeError):
    pass


GITIGNORE_BEGIN = "# BEGIN WM AI CODING"
GITIGNORE_END = "# END WM AI CODING"
MANAGED_GITIGNORE_BLOCK = """# BEGIN WM AI CODING
.wm/

# Keep only durable archived SDD artifacts in version control.
/sdd/changes/*
!/sdd/changes/archive/
!/sdd/changes/archive/**/
!/sdd/changes/archive/**/*
/sdd/changes/archive/**/tasks.md
/sdd/changes/archive/**/verification.md
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

    def _new_change(self, name: str) -> dict:
        return {
            "stage": self.workflow.initial,
            "status": "ready",
            "current_task": None,
            "completed_stages": [],
            "approvals": {},
            "baselines": {},
            "blocker": None,
            "last_handoff": None,
            "evidence_snapshot": inspect_change(self.repo / "sdd" / "changes" / name),
            "last_valid_stage": self.workflow.initial,
            "required_stage": None,
        }

    def _ensure_gitignore(self) -> bool:
        path = self.repo / ".gitignore"
        existing = path.read_text(encoding="utf-8") if path.is_file() else ""
        if MANAGED_GITIGNORE_BLOCK in existing:
            return False
        begin = existing.find(GITIGNORE_BEGIN)
        end = existing.find(GITIGNORE_END, begin + len(GITIGNORE_BEGIN)) if begin >= 0 else -1
        if begin >= 0:
            suffix_start = end + len(GITIGNORE_END) if end >= 0 else len(existing)
            if suffix_start < len(existing) and existing[suffix_start : suffix_start + 2] == "\r\n":
                suffix_start += 2
            elif suffix_start < len(existing) and existing[suffix_start] in "\r\n":
                suffix_start += 1
            updated = existing[:begin] + MANAGED_GITIGNORE_BLOCK + existing[suffix_start:]
        else:
            separator = "" if not existing or existing.endswith(("\n", "\r")) else "\n"
            updated = existing + separator + MANAGED_GITIGNORE_BLOCK
        path.write_text(updated, encoding="utf-8", newline="")
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
            if active_change or archived_record:
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
            raise MachineError("workflow checksum changed; migration required")
        return state

    def _select_change(self, state: dict, change: str | None) -> str:
        name = change or state.get("active_change")
        if not name or name not in state["changes"]:
            raise MachineError("select an active change")
        return name

    def status(self, change: str | None = None) -> dict:
        state = self._read()
        if change:
            self._select_change(state, change)
        return state

    def _write(self, state: dict, original_revision: int, event: str) -> dict:
        state["updated_at"] = now()
        return self.store.write(state, expected_revision=original_revision, event=event)

    def select(self, change: str) -> dict:
        state = self._read()
        if change not in state["changes"]:
            raise MachineError(f"unknown change: {change}")
        revision = state["revision"]
        state["active_change"] = change
        return self._write(state, revision, "change_selected")

    def reconcile(self, change: str | None = None) -> dict:
        state = self._read()
        revision = state["revision"]
        names = [change] if change else [path.name for path in self._change_dirs()]
        changed = False
        for name in names:
            if name not in state["changes"]:
                state["changes"][name] = self._new_change(name)
                changed = True
                continue
            item = state["changes"][name]
            evidence = inspect_change(self.repo / "sdd" / "changes" / name)
            approval = item.get("approvals", {}).get("design")
            baseline = item.get("baselines", {}).get("tasks")
            drifted = False
            if approval and approval.get("artifact_sha256") != evidence["design_digest"]:
                approval["status"] = "stale"
                drifted = True
            if baseline and baseline.get("artifact_sha256") != evidence["tasks_digest"]:
                baseline["status"] = "stale"
                drifted = True
            if drifted:
                item["status"] = "drifted"
                item["required_stage"] = "specify" if approval and approval.get("status") == "stale" else "tasks"
            if item.get("evidence_snapshot") != evidence:
                item["evidence_snapshot"] = evidence
                changed = True
            changed = changed or drifted
        return self._write(state, revision, "reconciled") if changed else state

    def approve_design(self, change: str | None = None) -> dict:
        state = self._read()
        revision = state["revision"]
        name = self._select_change(state, change)
        evidence = inspect_change(self.repo / "sdd" / "changes" / name)
        if not evidence["design_digest"]:
            raise MachineError("design.md is missing")
        state["changes"][name]["approvals"]["design"] = {
            "status": "approved", "source": "user", "artifact_sha256": evidence["design_digest"], "approved_at": now()
        }
        return self._write(state, revision, "design_approved")

    def baseline_tasks(self, change: str | None = None) -> dict:
        state = self._read()
        revision = state["revision"]
        name = self._select_change(state, change)
        evidence = inspect_change(self.repo / "sdd" / "changes" / name)
        if not evidence["task_contract_valid"]:
            raise MachineError("tasks.md does not satisfy the task contract")
        state["changes"][name]["baselines"]["tasks"] = {
            "status": "current", "artifact_sha256": evidence["tasks_digest"], "recorded_at": now()
        }
        return self._write(state, revision, "tasks_baselined")

    def _gate(self, gate: str, item: dict, evidence: dict) -> bool:
        return {
            "design_approved": item.get("approvals", {}).get("design", {}).get("status") == "approved",
            "codegraph_impact": evidence["codegraph_impact"],
            "planning_artifacts": evidence["proposal"] and evidence["specs"] and evidence["design"],
            "task_contract": evidence["task_contract_valid"],
            "task_baseline": item.get("baselines", {}).get("tasks", {}).get("status") == "current",
            "all_tasks_complete": evidence["tasks"] and evidence["open_tasks"] == 0,
            "verification": evidence["verification"],
            "codegraph_recheck": evidence["codegraph_recheck"],
        }[gate]

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
        missing = [gate for gate in current.exit_gates if not self._gate(gate, item, evidence)]
        if missing:
            raise MachineError("missing gates: " + ", ".join(missing))
        item["completed_stages"].append(item["stage"])
        item["stage"] = current.next
        item["last_valid_stage"] = current.next
        item["evidence_snapshot"] = evidence
        return self._write(state, revision, "advanced")

    def rewind(self, change: str | None, target: str, reason: str) -> dict:
        state = self._read()
        revision = state["revision"]
        name = self._select_change(state, change)
        if target not in self.workflow.states:
            raise MachineError(f"unknown target stage: {target}")
        item = state["changes"][name]
        item["stage"] = target
        item["status"] = "ready"
        item["required_stage"] = None
        item["approvals"] = {}
        item["baselines"] = {}
        item["completed_stages"] = []
        item["rewind_reason"] = reason
        return self._write(state, revision, "rewound")

    def block(self, change: str | None, reason: str) -> dict:
        state = self._read(); revision = state["revision"]; name = self._select_change(state, change)
        state["changes"][name]["status"] = "blocked"
        state["changes"][name]["blocker"] = {"reason": reason, "recorded_at": now()}
        return self._write(state, revision, "blocked")

    def resume(self, change: str | None) -> dict:
        state = self._read(); revision = state["revision"]; name = self._select_change(state, change)
        if state["changes"][name]["status"] != "blocked":
            raise MachineError("change is not blocked")
        state["changes"][name]["status"] = "ready"; state["changes"][name]["blocker"] = None
        return self._write(state, revision, "resumed")

    def validate(self) -> dict:
        state = self._read()
        findings: list[str] = []
        gitignore = self.repo / ".gitignore"
        if not gitignore.is_file() or MANAGED_GITIGNORE_BLOCK not in gitignore.read_text(encoding="utf-8"):
            findings.append("WM managed .gitignore policy is missing or incomplete")
        for name in state["changes"]:
            if not (self.repo / "sdd" / "changes" / name).is_dir():
                findings.append(f"missing change directory: {name}")
        return {"valid": not findings, "findings": findings, "state": state}
