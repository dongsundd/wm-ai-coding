"""Stable source paths and import setup shared by all development checks."""
from pathlib import Path
import sys

PLUGIN_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_ROOT = PLUGIN_ROOT / "scripts"
TESTS_ROOT = SCRIPTS_ROOT / "tests"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))
