#!/usr/bin/python3
"""Run the pinned ngspice binary with unchanged arguments and a live output copy."""
import os
from pathlib import Path
import sys
from command_log_tee import relay,finish

REAL=Path(__file__).resolve().parents[2]/'build/tools/ngspice47_klu_002/install/bin/ngspice'
args=sys.argv[1:]
if '-b' not in args:os.execv(REAL,[str(REAL),*args])
if len(args)!=2 or args[0]!='-b':raise SystemExit('one explicit batch deck required')
deck=Path(args[1]).resolve()
finish(relay([str(REAL),*args],deck.with_suffix('.live.log')))
