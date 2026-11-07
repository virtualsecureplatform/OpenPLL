"""Reassess one completed stress subset without changing source campaign receipts."""
import argparse
import json
import os
import time
from pathlib import Path
from common_v3 import save,sha,verify
from resources import lease
from reassess_selected_loop_exact_ps import run as reassess


def run(matrices,stress,output):
    if not matrices or len(set(matrices))!=len(matrices):raise ValueError('distinct source matrices required')
    output.mkdir(parents=True,exist_ok=False)
    sources=[Path(__file__).resolve(),Path(__file__).with_name('reassess_selected_loop_exact_ps.py'),Path(__file__).with_name('acceptance_v4.py')]
    rows=[]
    for i,matrix in enumerate(matrices):
        if json.loads((matrix/'status.json').read_text())['state']!='diagnostic_frequency_stress_matrix_assessed':raise ValueError('completed source campaign required')
        receipt=matrix/'assessment.json';cases=matrix/'cases.json'
        a=json.loads(receipt.read_text());verify(a['input_sha256']);verify(a['artifacts'])
        selected=[r for r in json.loads(cases.read_text())if r['stress']==stress]
        expected={(k,s,p)for k in ['linear_period','linear_frequency']for s in range(3)for p in [0,10,20,30]}
        if len(selected)!=24 or {(r['interpolation'],r['scenario'],r['phase_ns'])for r in selected}!=expected:raise ValueError('complete stress subset required')
        sources += [receipt,cases]
        for j,row in enumerate(selected):
            path=Path(row['assessment'])
            if sha(path)!=row['assessment_sha256']:raise ValueError('source case assessment changed')
            rows.append((i,j,row))
    pins={str(p):sha(p)for p in sources};records=[]
    save(output/'inputs.json',dict(input_sha256=pins,stress=stress,source_matrices=list(map(str,matrices)),expected_cases=len(rows),simulations_launched=0,release_ready=False))
    for i,j,row in rows:
        verify(pins)
        save(output/'status.json',dict(state='reassessing_saved_stress_traces',completed_cases=len(records),release_ready=False))
        result=reassess(Path(row['assessment']).parent,output/f'matrix{i}_case{j}')
        if result['prior_functional_trace_pass']!=result['recomputed_legacy_functional_trace_pass']:raise ValueError('legacy replay disagrees with source assessment')
        records.append(dict(source=row,prior_functional_trace_pass=result['prior_functional_trace_pass'],functional_trace_pass=result['functional_trace_pass'],assessment=str(output/f'matrix{i}_case{j}/assessment.json'),assessment_sha256=sha(output/f'matrix{i}_case{j}/assessment.json')))
        save(output/'cases.json',records)
    verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(output/'cases.json'):sha(output/'cases.json')},stress=stress,
        expected_cases=len(rows),completed_cases=len(records),prior_passes=sum(r['prior_functional_trace_pass']for r in records),exact_passes=sum(r['functional_trace_pass']for r in records),
        changed_cases=sum(r['prior_functional_trace_pass']!=r['functional_trace_pass']for r in records),
        limits_changed=False,original_runs_modified=False,simulations_launched=0,physical_models_qualified=False,release_ready=False))
    save(output/'status.json',dict(state='saved_stress_subset_reassessed',release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--matrix',action='append',type=Path,required=True);p.add_argument('--stress',choices=['nominal','gain','offset','gain_offset'],required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();os.sched_setaffinity(0,{30})
    with lease(1,2,time.clock_gettime(time.CLOCK_BOOTTIME)+1800):run([p.resolve()for p in a.matrix],a.stress,a.output.resolve())
