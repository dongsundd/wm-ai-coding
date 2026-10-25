"""Bounded concurrent acceptance checks in disjoint, host-prepared workspaces.

This module never launches agents or merges code. Each result identifies its workspace;
integration remains serial and requires fresh final verification in the target checkout.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import subprocess
import time
import tempfile
from pathlib import Path
from uuid import uuid4

from wm_ai_coding.evidence.runs import workspace_digest


def run_batch(jobs: list[dict], *, max_parallel: int = 2, timeout: float = 300) -> dict:
    if not isinstance(jobs, list) or not jobs or type(max_parallel) is not int or not 1 <= max_parallel <= 8 or not 0 < timeout <= 3600:
        raise ValueError("batch needs jobs, concurrency 1..8 and timeout 0..3600")
    roots=[]; tasks=set()
    for job in jobs:
        if not isinstance(job, dict) or not isinstance(job.get('workspace'), str):
            raise ValueError('invalid job')
        root=Path(job['workspace']).resolve()
        argv=job.get('argv')
        if (not root.is_dir() or not isinstance(job.get('task'),str) or job['task'] in tasks
                or job.get('depends_on') or not isinstance(argv,list) or not argv
                or not all(isinstance(x,str) and x for x in argv)):
            raise ValueError('jobs must be independent, uniquely identified and executable')
        if any(root.is_relative_to(p) or p.is_relative_to(root) for p in roots):
            raise ValueError('batch workspaces must be disjoint')
        roots.append(root);tasks.add(job['task'])
    batch_id=uuid4().hex
    def run(pair):
        job,root=pair; before=workspace_digest(root); start=time.monotonic()
        try:
            with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
                output=subprocess.run(job['argv'],cwd=root,stdin=subprocess.DEVNULL,stdout=out,stderr=err,timeout=timeout,check=False)
                code=output.returncode
                out.seek(max(0,out.tell()-4096));err.seek(max(0,err.tell()-4096))
                stdout=out.read().decode('utf-8',errors='replace');stderr=err.read().decode('utf-8',errors='replace')
        except (OSError,subprocess.TimeoutExpired) as exc:
            code=None;stdout='';stderr=str(exc)
        after=workspace_digest(root)
        return {'batch_id':batch_id,'task':job['task'],'workspace_id':str(root),'before':before,'after':after,
                'valid':code==0 and before==after,'exit_code':code,'duration_ms':round((time.monotonic()-start)*1000),
                'stdout_tail':stdout,'stderr_tail':stderr}
    with ThreadPoolExecutor(max_workers=max_parallel) as executor:
        results=list(executor.map(run,zip(jobs,roots)))
    return {'valid':all(r['valid'] for r in results),'batch_id':batch_id,'results':results,
            'integration':'serial; rerun final acceptance in target workspace; batch results do not advance tasks'}
