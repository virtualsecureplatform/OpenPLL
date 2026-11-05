"""Select the closest interpolated startup code for an unqualified model only."""
import argparse
import json
from pathlib import Path
from common_v3 import save,sha,verify

def run(base,output):
    m=json.loads(base.read_text());verify(m['input_sha256'])
    if m.get('synthetic') is not True or m.get('physical_models_qualified') is not False:raise ValueError('diagnostic model required')
    table=Path(m['dco_table']);rows=[list(map(int,line.split())) for line in table.read_text().splitlines()]
    if any(len(r)!=3 or r[0]!=m['coarse'] or not 8<=r[1]<=247 for r in rows):raise ValueError('supported calibrated table required')
    if not min(r[2] for r in rows)<400_000_000_000<max(r[2] for r in rows):raise ValueError('target bracket required')
    selected=min(rows,key=lambda r:(abs(r[2]-400_000_000_000),r[1]));m.update(seed=selected[1],startup_seed_native_measurement_qualified=False)
    m['input_sha256'].update({str(p):sha(p) for p in (base,Path(__file__).resolve())})
    output.mkdir(parents=True,exist_ok=False);save(output/'models.json',m)
    save(output/'assessment.json',dict(input_sha256=m['input_sha256'],artifacts={str(output/'models.json'):sha(output/'models.json')},seed=selected[1],interpolated_seed_frequency_millihz=selected[2],native_seed_capture_qualified=False,synthetic=True,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('base','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.base.resolve(),a.output.resolve())
