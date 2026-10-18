from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .machine import MachineError, StateMachine
from .store import RevisionConflict, StateError, StateLockTimeout
from .workflow import WorkflowError, load_workflow


def workflow_path() -> Path:
    candidates = []
    if configured := os.environ.get("WM_WORKFLOW_PATH"):
        candidates.append(Path(configured))
    candidates.extend(
        (
            Path(__file__).resolve().parents[2] / "skills" / "using-wm" / "workflow.yaml",
            Path(sys.prefix) / "share" / "wm-ai-coding" / "workflow.yaml",
        )
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise WorkflowError("using-wm workflow.yaml was not found")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="wm")
    root.add_argument("--repo", type=Path, default=Path.cwd())
    commands = root.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init"); init.add_argument("--no-gitignore", action="store_true")
    for name in ("status", "reconcile"):
        cmd = commands.add_parser(name); cmd.add_argument("--change")
    select = commands.add_parser("select"); select.add_argument("change")
    approve = commands.add_parser("approve"); approve.add_argument("kind", choices=["design"]); approve.add_argument("--change")
    baseline = commands.add_parser("baseline"); baseline.add_argument("kind", choices=["tasks"]); baseline.add_argument("--change")
    advance = commands.add_parser("advance"); advance.add_argument("--change")
    rewind = commands.add_parser("rewind"); rewind.add_argument("--change"); rewind.add_argument("--to", required=True); rewind.add_argument("--reason", required=True)
    block = commands.add_parser("block"); block.add_argument("--change"); block.add_argument("--reason", required=True)
    resume = commands.add_parser("resume"); resume.add_argument("--change")
    commands.add_parser("validate")
    workflow = commands.add_parser("workflow"); workflow.add_argument("action", choices=["show"])
    return root


def run(args: argparse.Namespace) -> dict:
    workflow = load_workflow(workflow_path())
    machine = StateMachine(args.repo, workflow)
    if args.command == "init": return machine.init(gitignore=not args.no_gitignore)
    if args.command == "status": return machine.status(args.change)
    if args.command == "select": return machine.select(args.change)
    if args.command == "reconcile": return machine.reconcile(args.change)
    if args.command == "approve": return machine.approve_design(args.change)
    if args.command == "baseline": return machine.baseline_tasks(args.change)
    if args.command == "advance": return machine.advance(args.change)
    if args.command == "rewind": return machine.rewind(args.change, args.to, args.reason)
    if args.command == "block": return machine.block(args.change, args.reason)
    if args.command == "resume": return machine.resume(args.change)
    if args.command == "validate": return machine.validate()
    if args.command == "workflow":
        return {"name": workflow.name, "initial": workflow.initial, "checksum": workflow.checksum, "states": {name: vars(state) for name, state in workflow.states.items()}}
    raise AssertionError(args.command)


def main(argv: list[str] | None = None) -> int:
    try:
        result = run(parser().parse_args(argv))
        print(json.dumps(result, ensure_ascii=False, indent=2, default=list))
        return 0
    except RevisionConflict as exc:
        print(json.dumps({"error": str(exc), "code": "revision_conflict"}), file=sys.stderr); return 5
    except (StateError, StateLockTimeout) as exc:
        print(json.dumps({"error": str(exc), "code": "state_error"}), file=sys.stderr); return 6
    except WorkflowError as exc:
        print(json.dumps({"error": str(exc), "code": "workflow_error"}), file=sys.stderr); return 7
    except MachineError as exc:
        message = str(exc); code = 8 if "approved" in message else 4
        print(json.dumps({"error": message, "code": "gate_error"}), file=sys.stderr); return code


if __name__ == "__main__":
    raise SystemExit(main())
