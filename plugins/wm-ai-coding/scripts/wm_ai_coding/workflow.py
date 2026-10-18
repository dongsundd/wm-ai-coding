from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class WorkflowError(ValueError):
    pass


@dataclass(frozen=True)
class WorkflowState:
    name: str
    skill: str
    next: str | None
    exit_gates: tuple[str, ...]
    terminal: bool = False
    repeat: str | None = None


@dataclass(frozen=True)
class Workflow:
    schema_version: int
    name: str
    initial: str
    gates: frozenset[str]
    states: dict[str, WorkflowState]
    checksum: str
    path: Path

    def next_state(self, state: str) -> str | None:
        try:
            return self.states[state].next
        except KeyError as exc:
            raise WorkflowError(f"unknown state: {state}") from exc


def load_workflow(path: Path) -> Workflow:
    raw = path.read_bytes()
    try:
        data: Any = yaml.safe_load(raw.decode("utf-8"))
    except (UnicodeDecodeError, yaml.YAMLError) as exc:
        raise WorkflowError(f"invalid workflow YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise WorkflowError("workflow must be a YAML object")
    initial = data.get("initial")
    state_data = data.get("states")
    gates_data = data.get("gates", [])
    if not isinstance(initial, str) or not isinstance(state_data, dict) or initial not in state_data:
        raise WorkflowError("workflow initial state is missing or unknown")
    if not isinstance(gates_data, list) or not all(isinstance(item, str) for item in gates_data):
        raise WorkflowError("workflow gates must be a string list")
    gates = frozenset(gates_data)
    states: dict[str, WorkflowState] = {}
    for name, config in state_data.items():
        if not isinstance(name, str) or not isinstance(config, dict):
            raise WorkflowError("workflow states must be objects")
        skill = config.get("skill")
        next_name = config.get("next")
        exit_gates = config.get("exit_gates", [])
        if not isinstance(skill, str):
            raise WorkflowError(f"state {name} has no skill")
        if next_name is not None and not isinstance(next_name, str):
            raise WorkflowError(f"state {name} has invalid next state")
        if not isinstance(exit_gates, list) or not all(item in gates for item in exit_gates):
            raise WorkflowError(f"state {name} has unknown exit gate")
        states[name] = WorkflowState(
            name=name,
            skill=skill,
            next=next_name,
            exit_gates=tuple(exit_gates),
            terminal=bool(config.get("terminal", False)),
            repeat=config.get("repeat"),
        )
    for state in states.values():
        if state.next is not None and state.next not in states:
            raise WorkflowError(f"state {state.name} points to unknown state {state.next}")
        if state.terminal and state.next is not None:
            raise WorkflowError(f"terminal state {state.name} cannot have next")
    return Workflow(
        schema_version=int(data.get("schema_version", 0)),
        name=str(data.get("name", "")),
        initial=initial,
        gates=gates,
        states=states,
        checksum=hashlib.sha256(raw).hexdigest(),
        path=path.resolve(),
    )

