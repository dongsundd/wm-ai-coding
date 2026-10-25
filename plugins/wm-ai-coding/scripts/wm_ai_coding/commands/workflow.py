from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from ..infrastructure.paths import workflow_path
from wm_ai_coding.lifecycle.machine import MachineError, StateMachine
from wm_ai_coding.infrastructure.store import RevisionConflict, StateError, StateLockTimeout
from wm_ai_coding.infrastructure.workflow import WorkflowError, load_workflow


def parser(*, include_tools: bool = False) -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="wm")
    root.add_argument("--repo", type=Path)
    commands = root.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init"); init.add_argument("--no-gitignore", action="store_true")
    for name in ("status", "reconcile"):
        cmd = commands.add_parser(name); cmd.add_argument("--change")
        if name == "status": cmd.add_argument("--json", action="store_true", help="JSON is the default output")
    select = commands.add_parser("select"); select.add_argument("change")
    approve = commands.add_parser("approve"); approve.add_argument("kind", choices=["design"]); approve.add_argument("--change")
    approve.add_argument("--reference", required=True, help="Existing user authorization or host approval event reference")
    condition = commands.add_parser("condition"); condition.add_argument("name", choices=["frontend_surface_changed"])
    condition.add_argument("value", choices=["true", "false"]); condition.add_argument("--change")
    check = commands.add_parser("check"); check.add_argument("check_id"); check.add_argument("--change")
    check.add_argument("--timeout", type=float, default=300)
    recovery = commands.add_parser("recovery"); recovery.add_argument("--change")
    handoff = commands.add_parser("handoff"); handoff.add_argument("--change")
    handoff.add_argument("--scope", nargs="+", required=True)
    handoff.add_argument("--skill", help="Registered stage/support/profile/operation")
    handoff.add_argument("--parent", help="Active parent handoff ID")
    finish = commands.add_parser("finish-handoff"); finish.add_argument("handoff_id"); finish.add_argument("--change")
    finish.add_argument("--result", choices=["completed", "blocked", "scope_changed", "failed"], required=True)
    finish.add_argument("--output", nargs="*", default=[]); finish.add_argument("--reason", default="")
    archive = commands.add_parser("archive"); archive.add_argument("--change")
    baseline = commands.add_parser("baseline"); baseline.add_argument("kind", choices=["tasks", "specs"]); baseline.add_argument("--change")
    advance = commands.add_parser("advance"); advance.add_argument("--change")
    rewind = commands.add_parser("rewind"); rewind.add_argument("--change"); rewind.add_argument("--to", required=True); rewind.add_argument("--reason", required=True)
    block = commands.add_parser("block"); block.add_argument("--change"); block.add_argument("--reason", required=True)
    resume = commands.add_parser("resume"); resume.add_argument("--change")
    commands.add_parser("validate")
    commands.add_parser("migrate")
    commands.add_parser("doctor")
    brief = commands.add_parser("brief"); brief.add_argument("--change")
    sync = commands.add_parser("sync"); sync.add_argument("--change")
    verify_archive = commands.add_parser("verify-archive"); verify_archive.add_argument("path", type=Path)
    review = commands.add_parser("review"); review.add_argument("--change"); review.add_argument("--file", type=Path, required=True)
    summary = commands.add_parser("verification-summary"); summary.add_argument("--change")
    batch = commands.add_parser("batch"); batch.add_argument("--file", type=Path, required=True); batch.add_argument("--max-parallel", type=int, default=2); batch.add_argument("--change")
    commands.add_parser("eval")
    workflow = commands.add_parser("workflow"); workflow.add_argument("action", choices=["show"])
    if include_tools:
        from .registry import register
        register(commands)
    return root


def run(args: argparse.Namespace) -> dict:
    workflow = load_workflow(workflow_path())
    machine = StateMachine(args.repo or Path.cwd(), workflow)
    if args.command == "init": return machine.init(gitignore=not args.no_gitignore)
    if args.command == "status": return machine.status(args.change)
    if args.command == "select": return machine.select(args.change)
    if args.command == "reconcile": return machine.reconcile(args.change)
    if args.command == "approve": return machine.approve_design(args.change, reference=args.reference)
    if args.command == "condition": return machine.set_frontend(args.change, args.value == "true")
    if args.command == "check": return machine.run_check(args.change, args.check_id, timeout=args.timeout)
    if args.command == "recovery": return machine.recovery(args.change)
    if args.command == "handoff": return machine.handoff(args.change, scope=args.scope, skill=args.skill, parent_id=args.parent)
    if args.command == "finish-handoff":
        return machine.finish_handoff(args.change, args.handoff_id, args.result, args.output, reason=args.reason)
    if args.command == "archive": return machine.archive(args.change)
    if args.command == "baseline":
        return machine.baseline_tasks(args.change) if args.kind == "tasks" else machine.baseline_specs(args.change)
    if args.command == "advance": return machine.advance(args.change)
    if args.command == "rewind": return machine.rewind(args.change, args.to, args.reason)
    if args.command == "block": return machine.block(args.change, args.reason)
    if args.command == "resume": return machine.resume(args.change)
    if args.command == "validate": return machine.validate()
    if args.command == "migrate": return machine.migrate()
    if args.command == "doctor":
        from wm_ai_coding.infrastructure.diagnostics import doctor
        return doctor(machine)
    if args.command == "brief":
        from wm_ai_coding.infrastructure.diagnostics import brief
        return brief(machine,args.change)
    if args.command == "sync": return machine.sync_specs(args.change)
    if args.command == "verify-archive":
        from wm_ai_coding.lifecycle.archives import verify_archive
        return verify_archive(args.path.resolve())
    if args.command == "review":
        from wm_ai_coding.evidence.reviews import record_review
        packet=machine.recovery(args.change)
        return record_review(machine.repo,machine._change_path(packet['change']),**json.loads(args.file.read_text(encoding='utf-8')))
    if args.command == "verification-summary":
        from wm_ai_coding.evidence.reviews import write_verification_summary
        packet = machine.recovery(args.change)
        return write_verification_summary(machine.repo, machine._change_path(packet['change']),
                                          frontend_changed=packet['conditions'].get('frontend_surface_changed') is True)
    if args.command == "batch":
        return machine.batch_checks(args.change,json.loads(args.file.read_text(encoding='utf-8')),max_parallel=args.max_parallel)
    if args.command == "eval":
        from wm_ai_coding.evidence.evaluations import evaluate
        return evaluate()
    if args.command == "workflow":
        return {
            "name": workflow.name,
            "initial": workflow.initial,
            "checksum": workflow.checksum,
            "states": {name: asdict(state) for name, state in workflow.states.items()},
        }
    raise AssertionError(args.command)


def execute(args: argparse.Namespace) -> int:
    try:
        result = run(args)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        if isinstance(result, dict) and (result.get("valid") is False or result.get("status") in {"failed", "timed_out", "cancelled"}):
            return 4
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
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc), "code": "input_error"}), file=sys.stderr); return 4


def main(argv: list[str] | None = None) -> int:
    return execute(parser().parse_args(argv))
