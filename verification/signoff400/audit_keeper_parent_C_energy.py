"""Exact small-support energy audit of the projected full parent C operator."""
import argparse,json
from fractions import Fraction as F
from pathlib import Path
from common_v3 import save,sha,verify
from audit_local_C_principal_energy import witness


def run(source,output):
    receipt=source/'assessment.json';r=json.loads(receipt.read_text());verify(r['input_sha256']);verify(r['artifacts'])
    file=source/'dynamic.pairs.jsonl';pairs={}
    for line in file.open():
        row=json.loads(line);key=tuple(row['nodes'])
        if key in pairs:raise ValueError('duplicate capacitor pair')
        pairs[key]=F(row['farads'])
    result=witness(pairs);output.mkdir(parents=True,exist_ok=False);folder=Path(__file__).resolve().parent
    pins={str(p):sha(p)for p in [receipt,file,Path(__file__).resolve(),folder/'audit_local_C_principal_energy.py']};verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={},result=result,models_modified=False,passivity_certified=False,parent_loading_complete=False,native_simulation_allowed=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.source.resolve(),a.output.resolve())
