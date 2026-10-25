from datetime import datetime, timezone

class MachineError(RuntimeError):
    pass


STAGE_ALIASES = {"impact": "specify"}
GITIGNORE_BEGIN = "# BEGIN WM AI CODING"
GITIGNORE_END = "# END WM AI CODING"
MANAGED_GITIGNORE_BLOCK = """# BEGIN WM AI CODING
.wm/

# Keep only durable archived SDD artifacts in version control.
/sdd/changes/*
!/sdd/changes/archive/
!/sdd/changes/archive/**/
!/sdd/changes/archive/**/*
# END WM AI CODING
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


