#!/usr/bin/env python3
"""Run a retained database-only KLayout helper under the available bindings."""
from pathlib import Path
import runpy
import sys
from klayout_compat import pya

if len(sys.argv)<2:
    raise SystemExit('usage: run_klayout_script.py SCRIPT [ARG ...]')
script=Path(sys.argv[1]).resolve()
sys.argv=sys.argv[1:]
sys.path.insert(0,str(script.parent))
runpy.run_path(str(script),run_name='__main__')
