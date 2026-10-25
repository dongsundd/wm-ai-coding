from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class WorkflowError(ValueError):
    pass


@dataclass(frozen=True)
class ConditionalSkill:
    when: str
    skill: str


@dataclass(frozen=True)
class WorkflowState:
    name: str
    skill: str
    next: str | None
    exit_gates: tuple[str, ...]
    terminal: bool = False
    repeat: str | None = None
    conditional_skills: tuple[ConditionalSkill, ...] = ()
    required_skills: tuple[str, ...] = ()


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
    if type(data.get("schema_version")) is not int or data["schema_version"] != 1:
        raise WorkflowError("unsupported workflow schema_version")
    initial = data.get("initial")
    state_data = data.get("states")
    gates_data = data.get("gates", [])
    if not isinstance(initial, str) or not isinstance(state_data, dict) or initial not in state_data:
        raise WorkflowError("workflow initial state is missing or unknown")
    if not isinstance(gates_data, list) or not all(isinstance(item, str) for item in gates_data):
        raise WorkflowError("workflow gates must be a string list")
    gates = frozenset(gates_data)
    known_gates = {"design_approved", "planning_artifacts", "structural_analysis", "frontend_design",
                   "task_contract", "task_baseline", "all_tasks_complete", "verification", "specs_synced"}
    if not gates <= known_gates:
        raise WorkflowError("workflow declares unsupported gates")
    states: dict[str, WorkflowState] = {}
    for name, config in state_data.items():
        if not isinstance(name, str) or not isinstance(config, dict):
            raise WorkflowError("workflow states must be objects")
        skill = config.get("skill")
        next_name = config.get("next")
        exit_gates = config.get("exit_gates", [])
        conditional_data = config.get("conditional_skills", [])
        required_data = config.get("required_skills", [])
        if (not isinstance(required_data, list) or not all(isinstance(s, str) and s for s in required_data)
                or len(required_data) != len(set(required_data))):
            raise WorkflowError(f"state {name} has invalid required skills")
        if not isinstance(skill, str) or not skill.strip():
            raise WorkflowError(f"state {name} has no skill")
        if next_name is not None and not isinstance(next_name, str):
            raise WorkflowError(f"state {name} has invalid next state")
        if not isinstance(exit_gates, list) or not all(isinstance(item, str) and item in gates for item in exit_gates):
            raise WorkflowError(f"state {name} has unknown exit gate")
        if not isinstance(conditional_data, list):
            raise WorkflowError(f"state {name} has invalid conditional skills")
        if type(config.get("terminal", False)) is not bool:
            raise WorkflowError(f"state {name} terminal must be boolean")
        conditional_skills: list[ConditionalSkill] = []
        for item in conditional_data:
            if not isinstance(item, dict) or not isinstance(item.get("when"), str) or not isinstance(item.get("skill"), str):
                raise WorkflowError(f"state {name} has invalid conditional skill")
            conditional_skills.append(ConditionalSkill(when=item["when"], skill=item["skill"]))
        states[name] = WorkflowState(
            name=name,
            skill=skill,
            next=next_name,
            exit_gates=tuple(exit_gates),
            terminal=bool(config.get("terminal", False)),
            repeat=config.get("repeat"),
            conditional_skills=tuple(conditional_skills),
            required_skills=tuple(required_data),
        )
        if config.get("repeat") not in (None, "per_task"):
            raise WorkflowError(f"unsupported repeat mode in {name}")
    for state in states.values():
        if state.next is not None and state.next not in states:
            raise WorkflowError(f"state {state.name} points to unknown state {state.next}")
        if state.terminal and state.next is not None:
            raise WorkflowError(f"terminal state {state.name} cannot have next")
        if not state.terminal and state.next is None:
            raise WorkflowError(f"nonterminal state {state.name} needs next")
    visited = set()
    cursor = initial
    while cursor is not None:
        if cursor in visited:
            raise WorkflowError("workflow contains a cycle")
        visited.add(cursor)
        cursor = states[cursor].next
    if visited != set(states):
        raise WorkflowError("workflow contains unreachable states")
    from wm_ai_coding.infrastructure.registry import alias_findings, find_registry_path
    registry = find_registry_path(path)
    if registry is not None:
        registry_data = yaml.safe_load(registry.read_text(encoding="utf-8"))
        registered = registry_data["skills"]
        if findings := alias_findings(registered, registry_data.get("aliases", {}), registry_data.get("stage_aliases", {})):
            raise WorkflowError("; ".join(findings))
        for name, state in states.items():
            for skill in [state.skill] + [c.skill for c in state.conditional_skills] + list(state.required_skills):
                if skill not in registered or name not in registered[skill].get("stages", []):
                    raise WorkflowError(f"unregistered stage skill: {skill}")
                if skill in state.required_skills and registered[skill].get("role") != "support":
                    raise WorkflowError(f"required skill must be support: {skill}")
    if data.get("protocol_version", 1) not in {1, 2}:
        raise WorkflowError("unsupported protocol version")
    return Workflow(
        schema_version=int(data.get("schema_version", 0)),
        name=str(data.get("name", "")),
        initial=initial,
        gates=gates,
        states=states,
        checksum=hashlib.sha256(raw + (registry.read_bytes() if registry.is_file() else b"" )).hexdigest(),
        path=path.resolve(),
    )
