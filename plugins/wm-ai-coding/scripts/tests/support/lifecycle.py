from __future__ import annotations
import json
from pathlib import Path
import tempfile
import unittest
from support.runtime import machine_for, write_change, advance_stage, advance_to_apply
from wm_ai_coding.lifecycle.machine import MachineError
from wm_ai_coding.infrastructure.registry import role_for


def specify(repo):
    change = write_change(repo)
    machine = machine_for(repo)
    machine.init(gitignore=False)
    advance_stage(machine)
    machine.set_frontend(None, False)
    return machine, change



def child(machine, parent, skill, output="design.md"):
    packet = machine.handoff(None, scope=parent['scope'], skill=skill, parent_id=parent['id'])
    machine.finish_handoff(None, packet['id'], 'completed', [f"sdd/changes/c1/{output}"])
    return packet

