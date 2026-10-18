from __future__ import annotations

import json
import os
import time
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
        if not isinstance(value, dict) or not isinstance(value.get("revision"), int):
            raise StateError("state.json has an invalid schema")
        return value

    @contextmanager
    def lock(self, timeout: float = 5.0) -> Iterator[None]:
        self.directory.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + timeout
        while True:
            try:
                fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, json.dumps({"pid": os.getpid(), "created_at": time.time()}).encode())
                os.close(fd)
                break
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise StateLockTimeout(f"timed out waiting for {self.lock_path}")
                time.sleep(0.05)
        try:
            yield
        finally:
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
            os.replace(temp, self.path)
            with self.events_path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps({"event": event, "revision": updated["revision"]}, ensure_ascii=False) + "\n")
            return updated

