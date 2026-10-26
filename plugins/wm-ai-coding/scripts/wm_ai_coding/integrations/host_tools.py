"""Normalize native tool arguments before policy; unknown tools are not approved."""
from dataclasses import dataclass
from pathlib import Path
import re


@dataclass(frozen=True)
class ToolOperation:
    kind: str
    targets: tuple[Path, ...] = ()
    command: str = ''
    workdir: Path | None = None


def _patch_targets(text: str) -> list[str]:
    if not isinstance(text, str) or not text.strip():
        raise ValueError('cannot determine patch targets')
    targets = []
    for line in text.splitlines():
        match = re.fullmatch(r'\*\*\* (?:Add File|Update File|Delete File|Move to): (.+)', line)
        if match:
            targets.append(match[1])
        elif line and not (line.startswith((' ', '+', '-', '@@')) or line in {
            '*** Begin Patch', '*** End Patch', '*** End of File',
        }):
            raise ValueError('unrecognized patch syntax; cannot establish all targets')
    if not targets:
        raise ValueError('cannot determine patch targets')
    return targets


def normalize_tool(payload: dict, repo: Path) -> ToolOperation:
    name = payload.get('tool_name', '')
    if not isinstance(name, str) or not name:
        raise ValueError('missing tool identity')
    name = name.rsplit('.', 1)[-1].lower()
    collaboration = {'collaboration'+action:action for action in
                     ('spawn_agent','wait','wait_agent','list_agents','send_input','send_message',
                      'close_agent','resume_agent','interrupt_agent','followup_task')}
    control = name in collaboration
    name = collaboration.get(name,name)
    args = payload.get('tool_input', {})
    if name in {'patch', 'apply_patch'} and isinstance(args, str):
        args = {'patch': args}
    if not isinstance(args, dict):
        raise ValueError('invalid tool input')
    if control:
        return ToolOperation('control')
    if 'codegraph' in name and re.search(r'(?:^|_)(?:explore|node|search|callers|callees|impact|files|status)$', name):
        return ToolOperation('read')
    if 'playwright' in name and re.search(r'(?:^|_)browser_(?:navigate|snapshot|tabs|close|resize|wait_for|click|type|press_key|select_option|hover|drag|evaluate|run_code|console_messages|network_requests|file_upload|handle_dialog|take_screenshot)$', name):
        # Browser effects remain governed by host/MCP permissions, not filesystem scope.
        # Explicit screenshot output targets still go through filesystem policy below.
        if name.endswith('browser_take_screenshot') and args.get('filename'):
            name, args = 'write', {'path':args['filename']}
        else:
            return ToolOperation('external')
    cwd = payload.get('cwd') or str(repo)
    if not isinstance(cwd, str):
        raise ValueError('invalid cwd')
    base = Path(cwd).resolve()
    if name in {'bash', 'powershell', 'exec_command', 'shell'}:
        command = args.get('command', args.get('cmd', ''))
        if not isinstance(command, str) or not command.strip():
            raise ValueError('invalid shell command')
        # A workdir override changes how every relative shell argument resolves.
        workdir = args.get('workdir', args.get('cwd', str(base)))
        if not isinstance(workdir, str) or not workdir.strip():
            raise ValueError('invalid shell workdir')
        return ToolOperation('shell', command=command, workdir=(base / workdir).resolve())
    if name in {'patch', 'apply_patch'}:
        text = args.get('patchText', args.get('patch', args.get('input', args.get('command', ''))))
        paths = _patch_targets(text)
    elif name in {'move', 'rename'}:
        paths = [args.get('source'), args.get('destination')]
    elif name in {'write', 'edit', 'delete', 'remove', 'multi_edit', 'multiedit', 'notebookedit'}:
        paths = [args.get('file_path') or args.get('filePath') or args.get('path') or args.get('notebook_path')]
    elif name in {'read', 'grep', 'glob', 'ls', 'list', 'search', 'webfetch', 'websearch', 'skill',
                  'askuserquestion', 'exitplanmode', 'enterplanmode', 'todowrite', 'todoread',
                  'taskcreate', 'taskupdate', 'tasklist', 'taskget', 'agent', 'task', 'subagent',
                  'request_user_input', 'update_plan', 'spawn_agent', 'wait', 'wait_agent',
                  'send_input', 'close_agent', 'resume_agent'}:
        return ToolOperation('read')
    else:
        raise ValueError(f'unsupported tool {name}; host review or an explicit adapter is required')
    if not all(isinstance(value, str) and value.strip() and '\x00' not in value for value in paths):
        raise ValueError('write needs explicit non-empty target paths')
    return ToolOperation('write', tuple((base / value).resolve() for value in paths))
