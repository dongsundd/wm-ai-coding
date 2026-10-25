"""Install a built wheel into a temporary environment and test installed data discovery."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import venv


def main(wheel: Path):
    if not wheel.is_file():
        raise ValueError("wheel does not exist")
    with tempfile.TemporaryDirectory(prefix='wm-wheel-smoke-') as temporary:
        root=Path(temporary);envroot=root/'env'
        venv.create(envroot,system_site_packages=True,with_pip=True)
        python=envroot/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
        env=dict(os.environ);env.pop('PYTHONPATH',None)
        subprocess.run([str(python),'-m','pip','install','--no-deps','--no-index',str(wheel.resolve())],
                       check=True,timeout=60,env=env,cwd=root)
        code='''
from pathlib import Path
import sys
import wm_ai_coding
from wm_ai_coding.cli import workflow_path, main
from wm_ai_coding.workflow import load_workflow
from wm_ai_coding.registry import role_for
assert Path(wm_ai_coding.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
workflow=load_workflow(workflow_path())
assert role_for(workflow,'python-ai-coding','apply') == 'profile'
assert main(['--repo',str(Path.cwd()),'init','--no-gitignore']) == 0
assert main(['--repo',str(Path.cwd()),'status']) == 0
'''
        subprocess.run([str(python),'-c',code],check=True,timeout=30,env=env,cwd=root)
    print(json.dumps({'valid':True,'wheel':wheel.name,'installed_data_and_cli':'passed'}))


if __name__=='__main__':
    main(Path(sys.argv[1]))
