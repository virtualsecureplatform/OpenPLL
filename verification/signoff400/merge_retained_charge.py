#!/usr/bin/env python3
"""Run the established map/ledger merge in a separately bounded process."""
import argparse
import json
from pathlib import Path
import sys
from common import ROOT
sys.path.append(str(ROOT/'verification/prototype400'))
sys.path.append(str(ROOT/'verification/timing400'))
from compile_capacitance_parallel import merge

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',required=True,type=Path)
    p.add_argument('--receipts',required=True,type=Path)
    a=p.parse_args();merge(a.output,json.loads(a.receipts.read_text()))
