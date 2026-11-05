#!/usr/bin/env python3
"""Reject unresolved equal-time threshold events and backwards time."""
import json
from pathlib import Path
import tempfile
import time
from assess_compact_numerical_holdout_v2 import assess
from compile_local_C_operators_v2 import digest,save

root=Path(__file__).resolve().parents[2]
out=root/'build/timing400/release_001/printed_time_holdout_parser_checks_001'
out.mkdir(exist_ok=False)
source=root/'build/timing400/release_001/selected_compact_numerical_holdouts_sf_m40_001/relative_tolerance_only'
plan=json.loads((source/'plan.json').read_text())
lines=(source/'run_001/batch.prn').read_text().splitlines(True)
rows=[i for i,line in enumerate(lines) if line.split() and line.split()[0].isdigit()]
target=next(b for a,b in zip(rows,rows[1:]) if lines[a].split()[1]==lines[b].split()[1])
checks=[]
for label in ('threshold_straddle','backwards_time'):
    with tempfile.TemporaryDirectory() as folder:
        p=Path(folder);modified=list(lines); row=modified[target].split()
        if label=='threshold_straddle':
            prior=modified[target-1].split();prior[2]='0.8';row[2]='1.0'
            modified[target-1]=' '.join(prior)+'\n'
        else: row[1]=str(float(row[1])-1e-9)
        modified[target]=' '.join(row)+'\n'
        (p/'batch.prn').write_text(''.join(modified))
        try: assess(plan,{},p,time.clock_gettime(time.CLOCK_BOOTTIME)+60)
        except AssertionError as error: checks.append(dict(case=label,rejected=True,reason=str(error)))
        else: raise AssertionError('unsafe trace accepted: '+label)
save(out/'assessment.json',dict(checks=checks,input_sha256={str(p):digest(p) for p in
    (Path(__file__).resolve(),Path(__file__).with_name('assess_compact_numerical_holdout_v2.py'),source/'run_001/batch.prn')},
    native_started=False,release_qualified=False))
print(json.dumps(checks))
