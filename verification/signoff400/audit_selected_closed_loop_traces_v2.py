"""Recompute functional limits from a closed-loop receipt's pinned raw traces."""
import csv
from pathlib import Path
from acceptance_v4 import evaluate
from common_v3 import verify
from selected_reference_phase import assess as assess_phase


def case_traces(receipt,case,profile):
    scenario=profile['scenarios'].index(case['scenario'])
    phase=case['phase_offset_ns']
    if type(phase) is not int or phase not in profile['reference_phase_offsets_ns']:
        raise ValueError('declared integer phase coordinate required')
    suffix=f'/{case["scenario"]}_phase{phase}/edges.csv'
    matches=[Path(p) for p in receipt['artifacts'] if ('/'+p.lstrip('/')).endswith(suffix)]
    if len(matches)!=1:raise ValueError('one pinned raw edge trace per closed-loop case required')
    directory=matches[0].parent
    for name in ['edges.csv','controls.csv','segments.csv','run.log']:
        if str(directory/name) not in receipt['artifacts']:raise ValueError('all raw closed-loop traces must be pinned')
    pins={str(directory/name):receipt['artifacts'][str(directory/name)] for name in ['edges.csv','controls.csv','segments.csv','run.log']}
    verify(pins)
    if case.get('native_exit')!=0 or f'PROGRAMMED400_LOOP_END scenario={scenario}' not in (directory/'run.log').read_text():
        raise ValueError('normal closed-loop completion required')
    events={name:[] for name in ['REF','DIV','OUT']}
    with (directory/'edges.csv').open() as f:
        for row in csv.DictReader(f):
            if row['event'] not in events:raise ValueError('unknown raw clock event')
            events[row['event']].append([float(row['time_ns']),int(row['code']),int(row['bbpd'])])
    controls=[]
    with (directory/'controls.csv').open() as f:
        for row in csv.DictReader(f):
            if row['event']=='ERROR':raise ValueError('closed-loop driver reported an error')
            if row['event']=='TUNE':controls.append([int(row['time_ps'])/1000,int(row['fine'])])
    with (directory/'segments.csv').open() as f:segments=list(csv.DictReader(f))
    count=1 if scenario==0 else 2
    if [int(row['segment']) for row in segments]!=list(range(count)):
        raise ValueError('complete raw closed-loop scenario segments required')
    for segment in segments:
        start,stop=float(segment['enabled_ns']),float(segment['stop_ns'])
        if stop-start<220000:raise ValueError('truncated raw closed-loop scenario')
        result=evaluate(events,controls,profile['target_mhz'],start,stop,profile)
        if result['passed'] is not True:raise ValueError('raw closed-loop trace fails functional limits')
    phase_result=assess_phase(directory,scenario,phase)
    if phase_result['reference_phase_coverage_pass'] is not True:
        raise ValueError('raw trace does not demonstrate requested reference phase')
    if phase_result['initializations']!=case['reference_phase_initializations']:
        raise ValueError('receipt phase coordinates differ from raw trace')
    verify(pins)
    return True


def check(receipt,profile):
    for case in receipt['records']:case_traces(receipt,case,profile)
