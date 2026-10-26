"""Parse hook invocations and translate JSON streams at the CLI boundary."""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import sys

from ..integrations.hook_bridge import dispatch, failure
from ..integrations.hooks import CAPABILITIES


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("host", choices=sorted(CAPABILITIES))
    parser.add_argument("event")


def run(args: argparse.Namespace) -> int:
    # Plugin bridges exchange UTF-8 JSON even on a Windows legacy-codepage console.
    for stream in (sys.stdin, sys.stdout):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    payload = {}
    try:
        payload = json.load(sys.stdin)
        result = dispatch(args.host, args.event, payload, repo=getattr(args, "repo", None))
    except Exception as exc:
        # Hook execution failures must remain valid host protocol responses.
        result = failure(args.host, args.event, exc)
    if trace_path := os.environ.get('WM_HOOK_TRACE'):
        # Explicit diagnostics only. Never persist arbitrary tool input or credentials.
        context = result.get('context', result.get('hookSpecificOutput', {}).get('additionalContext', ''))
        trace = {'time': datetime.now(timezone.utc).isoformat(), 'host': args.host, 'event': args.event,
                 'session_id': payload.get('session_id') if isinstance(payload, dict) else None,
                 'tool': payload.get('tool_name') if isinstance(payload, dict) else None,
                 'cwd': payload.get('cwd') if isinstance(payload, dict) else None,
                 'bootstrap': 'WM_BOOTSTRAP' in context, 'worker': 'WM_WORKER' in context,
                 'allowed': result.get('allowed'),
                 'permissionDecision': result.get('hookSpecificOutput', {}).get('permissionDecision')}
        if isinstance(payload, dict):
            trace['source'] = payload.get('source', payload.get('trigger'))
        brief_text = context.split('WM current state: ', 1)[-1]
        try:
            state_brief = json.loads(brief_text)
            if isinstance(state_brief, dict):
                trace['state'] = {key:state_brief.get(key) for key in ('change','stage','status','task')}
        except ValueError:
            pass
        try:
            with Path(trace_path).open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(trace, ensure_ascii=True) + '\n')
        except OSError as exc:
            print(f'WM trace unavailable: {exc}', file=sys.stderr)
    print(json.dumps(result, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wm hook")
    parser.add_argument("--repo", type=Path)
    add_arguments(parser)
    return run(parser.parse_args(argv))
