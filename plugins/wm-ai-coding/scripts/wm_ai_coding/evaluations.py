"""Deterministic protocol evaluations. This does not score a model's skill selection."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path


def evaluate() -> dict:
    from .archives import write_manifest, verify_archive
    from .cli import workflow_path
    from .workflow import load_workflow
    from .machine import StateMachine, MachineError
    from .hooks import handle_hook
    from .specs import expected_specs
    from .evidence import ready_tasks
    cases=[]
    def record(name, passed):
        cases.append({'name':name,'passed':bool(passed)})
    with tempfile.TemporaryDirectory() as directory:
        repo=Path(directory); m=StateMachine(repo,load_workflow(workflow_path()));m.init(gitignore=False)
        try:m.reconcile('../../escape')
        except MachineError:record('reject-process-path-escape',True)
        else:record('reject-process-path-escape',False)
        record('pause-does-not-require-completion',handle_hook(m,'codex','Stop',{'intent':'pause'})=={})
        record('empty-task-graph-has-no-ready-task',ready_tasks([])==[])
        graph=[{'id':'task-1','complete':False,'depends_on':['task-2']},{'id':'task-2','complete':False,'depends_on':[]}]
        record('route-only-ready-dependency',ready_tasks(graph)[0]['id']=='task-2')
        archive=repo/'archive';archive.mkdir();(archive/'proof.txt').write_text('original')
        seal=write_manifest(archive);record('portable-archive-accepts-intact-assets',verify_archive(archive,seal)['valid'])
        (archive/'proof.txt').write_text('changed');record('portable-archive-rejects-tampering',not verify_archive(archive,seal)['valid'])
        try:expected_specs({}, {'a/spec.md':'## MODIFIED Requirements\n### Requirement: absent\nNew.\n'})
        except ValueError:record('sync-rejects-missing-preimage',True)
        else:record('sync-rejects-missing-preimage',False)
        record('host-capabilities-do-not-invent-taskcompleted','TaskCompleted' not in __import__('wm_ai_coding.hooks',fromlist=['CAPABILITIES']).CAPABILITIES['codex']['events'])
    return {'valid':all(c['passed'] for c in cases),'cases':cases,
            'scope':'deterministic runtime contracts; live model routing/token/host-session evaluation requires host runs'}
