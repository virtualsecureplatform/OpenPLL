"""Inspect the completed native unit fixture after handling its legal terminal .end."""
from pathlib import Path
import json
from fractions import Fraction as F
from runtime_common import ROOT,save,sha
from resources import identity
from audit_keeper_native_R_contraction import parse

def run():
    source=ROOT/'build/signoff400/selected_wire_R_units_1676';out=ROOT/'build/signoff400/selected_wire_R_unit_assessment_1677';out.mkdir(exist_ok=False)
    worker=json.loads((source/'native.process.json').read_text())
    if identity(worker['pid'])==worker['birth']:raise ValueError('native fixture still active')
    if 'exttospice finished.' not in (source/'native.log').read_text():raise ValueError('completed native output required')
    text='\n'.join(l for l in (source/'wire.spice').read_text().splitlines() if l.strip().lower()!='.end')
    actual={tuple(sorted([a,b])):v for a,b,v in parse(text)['resistors']}
    values=[('a','b','0'),('c','d','0.000001'),('e','f','4.975'),('g','h','1000')];results=[]
    for a,b,v in values:
        expected=F(v);observed=actual[tuple(sorted([a,b]))]
        results.append(dict(nodes=[a,b],native_EXT_R_ohm_exact=str(expected),exported_R_ohm_exact=str(observed),error_ohm_exact=str(observed-expected)))
    paths=[p for p in source.iterdir() if p.is_file()]+[Path(__file__).resolve(),ROOT/'verification/signoff400/probe_wire_R_units_1676.py']
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in paths},native_terminal_end_directive_accepted=True,results=results,zero_ohm_changed_to_positive=actual['a','b']>0,native_wire_units_exact=all(r['error_ohm_exact']=='0' for r in results),RC_export_fixed=False,release_ready=False))
if __name__=='__main__':run()
