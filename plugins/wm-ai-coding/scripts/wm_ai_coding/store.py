from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class StateError(RuntimeError):
    pass


class RevisionConflict(StateError):
    pass


class StateLockTimeout(StateError):
    pass


class StateStore:
    def __init__(self, repo: Path):
        self.repo = repo.resolve()
        self.directory = self.repo / ".wm"
        self.path = self.directory / "state.json"
        self.lock_path = self.directory / "state.lock"
        self.events_path = self.directory / "events.jsonl"

    def read(self) -> dict:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise StateError("state is not initialized; run wm init") from exc
        except json.JSONDecodeError as exc:
            recovery = self.directory / "recovery"
            recovery.mkdir(parents=True, exist_ok=True)
            backup = recovery / f"state-corrupt-{int(time.time())}.json"
            backup.write_bytes(self.path.read_bytes())
            raise StateError(f"state.json is corrupt; backup: {backup}") from exc
        if (not isinstance(value, dict) or type(value.get("revision")) is not int
                or value["revision"] < 0 or value.get("schema_version") != 1
                or not isinstance(value.get("changes"), dict) or not isinstance(value.get("workflow"), dict)):
            raise StateError("state.json has an invalid schema")
        for name, item in value["changes"].items():
            if (not isinstance(name, str) or not isinstance(item, dict)
                    or not isinstance(item.get("stage"), str)
                    or item.get("status") not in {"ready", "blocked", "drifted", "archived"}
                    or not isinstance(item.get("approvals"), dict)
                    or not isinstance(item.get("baselines"), dict)
                    or not isinstance(item.get("completed_stages"), list)):
                raise StateError(f"state.json has an invalid change: {name}")
        return value

    def _lock_is_stale(self, stale_after: float) -> bool:
        try:
            data = json.loads(self.lock_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return False
        except (OSError, json.JSONDecodeError):
            data = {}
        created_at = data.get("created_at")
        age = time.time() - created_at if isinstance(created_at, (int, float)) else None
        if age is None:
            try:
                age = time.time() - self.lock_path.stat().st_mtime
            except OSError:
                return False
        pid = data.get("pid")
        if os.name != "nt" and isinstance(pid, int):
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return True
            except PermissionError:
                return False
            else:
                return False  # A live owner never expires by age alone.
        if os.name == "nt" and isinstance(pid, int):
            import ctypes
            handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
            if handle:
                try:
                    code = ctypes.c_ulong()
                    if ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                        return code.value != 259
                    return False
                finally:
                    ctypes.windll.kernel32.CloseHandle(handle)
            if ctypes.windll.kernel32.GetLastError() == 5:
                return False  # Permission denied is not proof of death.
        return age is not None and age > stale_after

    @contextmanager
    def lock(self, timeout: float = 5.0, stale_after: float = 60.0) -> Iterator[None]:
        self.directory.mkdir(parents=True, exist_ok=True)
        token = f"{os.getpid()}-{time.time_ns()}"
        deadline = time.monotonic() + timeout
        while True:
            try:
                fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(
                    fd,
                    json.dumps(
                        {"pid": os.getpid(), "created_at": time.time(), "token": token}
                    ).encode(),
                )
                os.close(fd)
                break
            except FileExistsError:
                if self._lock_is_stale(stale_after):
                    self.lock_path.unlink(missing_ok=True)
                    continue
                if time.monotonic() >= deadline:
                    raise StateLockTimeout(f"timed out waiting for {self.lock_path}")
                time.sleep(0.05)
        try:
            yield
        finally:
            try:
                data = json.loads(self.lock_path.read_text(encoding="utf-8"))
            except FileNotFoundError:
                data = {}
            except (OSError, json.JSONDecodeError):
                data = {}
            if data.get("token") == token:
                self.lock_path.unlink(missing_ok=True)

    def write(self, state: dict, *, expected_revision: int, event: str = "state_updated") -> dict:
        with self.lock():
            current = self.read() if self.path.exists() else None
            actual = current["revision"] if current else 0
            if actual != expected_revision:
                raise RevisionConflict(f"expected revision {expected_revision}, found {actual}")
            updated = json.loads(json.dumps(state))
            updated["revision"] = actual + 1
            self.directory.mkdir(parents=True, exist_ok=True)
            (self.directory / "tmp").mkdir(exist_ok=True)
            temp = self.directory / "tmp" / f"state-{os.getpid()}.json"
            with temp.open("w", encoding="utf-8", newline="\n") as handle:
                json.dump(updated, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            before = current.get("changes", {}) if current else {}
            changes = {name: {"stage": item.get("stage"), "status": item.get("status"),
                              "task": item.get("current_task"),
                              "handoff": {k:v for k,v in (item.get("last_handoff") or {}).items() if k != "files_before"},
                              "blocker": item.get("blocker")}
                       for name, item in updated.get("changes", {}).items() if before.get(name) != item}
            entry = {"event": event, "revision": updated["revision"],
                     "trace_id": f"state-{updated['revision']}",
                     "timestamp": datetime.now(timezone.utc).isoformat(), "changes": changes}
            outbox = self.directory / "outbox"; outbox.mkdir(exist_ok=True)
            pending = outbox / f"{updated['revision']:020d}.json"
            pending.write_text(json.dumps(entry, ensure_ascii=False), encoding="utf-8")
            os.replace(temp, self.path)
            # A committed state stays successful even when diagnostics cannot be flushed.
            try:
                self._flush_events_locked()
            except OSError:
                pass  # Pending outbox is durable and replayed by the next write/flush.
            return updated

    def _append_event(self, entry: dict) -> None:
        with self.events_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
            handle.flush(); os.fsync(handle.fileno())

    def _flush_events_locked(self) -> None:
        committed = self.read()["revision"] if self.path.exists() else 0
        existing = set()
        if self.events_path.exists():
            lines = self.events_path.read_text(encoding="utf-8").splitlines()
            valid = []
            for line in lines:
                try:
                    record = json.loads(line); existing.add(record["revision"]); valid.append(line)
                except (ValueError, KeyError, TypeError):
                    recovery = self.directory / "recovery"; recovery.mkdir(exist_ok=True)
                    (recovery / f"events-corrupt-{time.time_ns()}.txt").write_text(line, encoding="utf-8")
            if len(valid) != len(lines):
                self.events_path.write_text("\n".join(valid) + ("\n" if valid else ""), encoding="utf-8")
        for pending in sorted((self.directory / "outbox").glob("*.json")):
            entry = json.loads(pending.read_text(encoding="utf-8"))
            if entry["revision"] > committed:
                continue
            if entry["revision"] not in existing:
                self._append_event(entry); existing.add(entry["revision"])
            pending.unlink()

    def flush_events(self) -> None:
        with self.lock():
            self._flush_events_locked()
