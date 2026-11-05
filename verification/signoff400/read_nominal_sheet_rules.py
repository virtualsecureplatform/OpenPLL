#!/usr/bin/env python3
"""Read documented nominal rules inside the pinned PDK environment."""
import argparse
from pathlib import Path
from common import save,sha
from nominal_sheet_resistance import parse

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--tech',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    a=p.parse_args()
    if a.output.exists():raise FileExistsError('fresh nominal sheet output required')
    values=parse(a.tech.read_text())
    save(a.output,dict(unit='milliohms_per_square',values={k:str(v) for k,v in values.items()},
        tech_path=str(a.tech.absolute()),tech_sha256=sha(a.tech),
        input_sha256={str(q.resolve()):sha(q) for q in (Path(__file__),Path(__file__).with_name('nominal_sheet_resistance.py'))},
        reference_temperature_known=False,resistance_PVT_qualified=False))
