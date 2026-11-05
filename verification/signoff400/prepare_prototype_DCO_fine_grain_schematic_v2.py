"""Halve each fine-code load step while retaining all 510 physical load cells."""
import argparse
import json
from pathlib import Path
from common_v3 import save,sha,verify

def revise(text):
    for i in range(510):
        before=f'Xfine_{i} DCO_THERM[{i//2}] '
        if text.count(before)!=1:raise ValueError('exact two-load-per-code source required')
        if i%2!=(i//2)%2:text=text.replace(before,f'Xfine_{i} VPWR ')
    return text

def run(source,output):
    receipt=source/'assessment.json';a=json.loads(receipt.read_text());verify(a['input_sha256']);verify(a['artifacts'])
    if not a['schematic_only'] or (a['fine_loads'],a['controlled_inverting_stages'],a['always_enabled_units_per_stage'])!=(510,2,8):raise ValueError('checked 510-load two-stage baseline required')
    original=source/'schematic.spice';text=revise(original.read_text());output.mkdir(parents=True,exist_ok=False);model=output/'schematic.spice';model.write_text(text)
    inputs={str(p):sha(p) for p in (receipt,original,Path(__file__).resolve())}
    a.update(input_sha256=inputs,artifacts={str(model):sha(model)},variable_fine_loads=255,fixed_low_fine_loads=0,fixed_high_fine_loads=255,variable_loads_per_fine_code=1,variable_stage_alternates_with_code_parity=True,architecture_selected=False,analog_tuning_qualified=False,release_ready=False)
    save(output/'assessment.json',a)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('source','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.source.resolve(),a.output.resolve())
