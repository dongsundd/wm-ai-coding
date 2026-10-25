from __future__ import annotations

import re

from wm_ai_coding.evidence.inspection import artifact_tree_digest, inspect_change
from wm_ai_coding.infrastructure.registry import canonical_skill
from wm_ai_coding.lifecycle.archives import integrity_for, export_evidence, write_manifest
from wm_ai_coding.lifecycle.specs import read_tree, expected_specs


from .common import MachineError, now

class ClosureOperations:
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


