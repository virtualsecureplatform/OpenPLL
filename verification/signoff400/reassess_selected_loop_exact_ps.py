"""Reassess completed loop traces in fresh outputs; never alter the original run."""
import argparse
import csv
import json
import os
import time
from pathlib import Path
from common_v3 import save,sha,verify,spec,PROFILE
from acceptance_v4 import evaluate
from acceptance_v3 import evaluate as legacy_evaluate
from selected_reference_phase import assess as phase_assess
from resources import lease


def run(case,output):
    if output.exists():raise FileExistsError(output)
    old=json.loads((case/'assessment.json').read_text())
    scenario=old['scenario'];phase=old['phase_offset_ns']
    if old.get('native_exit')!=0 or not old.get('terminal_marker_present') or old.get('measurement_requests'):
        raise ValueError('normally completed trace without missing model lookups required')
    if f'PROGRAMMED400_LOOP_END scenario={scenario}'not in (case/'run.log').read_text():raise ValueError('actual completion marker required')
    inputs=json.loads((case/'inputs.json').read_text());verify(inputs['input_sha256'])
    paths=[case/n for n in ['assessment.json','inputs.json','run.log','edges.csv','controls.csv','segments.csv']]
    paths += [Path(__file__).resolve(),PROFILE,Path(__file__).with_name('acceptance_v4.py'),Path(__file__).with_name('acceptance_v3.py'),Path(__file__).with_name('selected_reference_phase.py')]
    pins={str(p):sha(p)for p in paths}
    events={k:[]for k in ['REF','DIV','OUT']};tunes=[]
    for row in csv.DictReader((case/'edges.csv').open()):events[row['event']].append([float(row['time_ns']),int(row['code']),int(row['bbpd'])])
    for row in csv.DictReader((case/'controls.csv').open()):
        if row['event']=='ERROR':raise ValueError('model driver error')
        if row['event']=='TUNE':tunes.append([int(row['time_ps'])/1000,int(row['fine'])])
    segments=list(csv.DictReader((case/'segments.csv').open()))
    if [int(r['segment'])for r in segments]!=list(range(1 if scenario==0 else 2)):raise ValueError('complete scenario segments required')
    phase_result=phase_assess(case,scenario,phase)
    output.mkdir(parents=True)
    reports=[]
    for row in segments:
        start,stop=float(row['enabled_ns']),float(row['stop_ns'])
        if stop-start<220000:raise ValueError('complete observation horizon required')
        arguments=(events,tunes,400,start,stop,spec())
        prior=legacy_evaluate(*arguments);current=evaluate(*arguments)
        i=int(row['segment'])
        save(output/f'legacy_segment{i}.json',prior);save(output/f'exact_segment{i}.json',current)
        reports.append(dict(segment=i,legacy_pass=prior['passed'],exact_pass=current['passed'],
            exact_statistics_in_every_window=all(w.get('phase_statistics_method')=='exact_integer_picosecond_grid'for w in current['windows']),
            acquisition_confirmed_ns=current['acquisition_confirmed_ns']))
    verify(pins);verify(inputs['input_sha256'])
    artifacts={str(p):sha(p)for p in output.glob('*.json')}
    result=dict(input_sha256=pins,artifacts=artifacts,original_case=str(case),records=reports,
        prior_functional_trace_pass=old['functional_trace_pass'],recomputed_legacy_functional_trace_pass=all(r['legacy_pass']for r in reports)and phase_result['reference_phase_coverage_pass'],
        functional_trace_pass=all(r['exact_pass']for r in reports)and phase_result['reference_phase_coverage_pass'],
        reference_phase=phase_result,original_run_modified=False,simulations_launched=0,
        acceptance_limits_changed=False,absolute_or_relative_epsilon_added=False,
        physical_models_qualified=False,release_ready=False)
    save(output/'assessment.json',result)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ['case','output']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();os.sched_setaffinity(0,{30})
    with lease(1,2,time.clock_gettime(time.CLOCK_BOOTTIME)+600):r=run(a.case.resolve(),a.output.resolve())
    print(json.dumps({k:r[k]for k in ['prior_functional_trace_pass','recomputed_legacy_functional_trace_pass','functional_trace_pass']}))
