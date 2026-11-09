"""Functional assessment for selected mixed-signal runs; never physical signoff."""
import csv
from common_v3 import save
from reset_contract_v4 import spec
from acceptance_v5 import evaluate


def assess(output,exit_code,scenario):
    result=dict(functional_trace_pass=False,segments=[],physical_models_qualified=False,release_ready=False)
    marker=f'PROGRAMMED400_LOOP_END scenario={scenario}'
    if exit_code!=0 or marker not in (output/'run.log').read_text():
        return dict(result,failure='native_exit_or_completion_marker')
    events={k:[] for k in ['REF','DIV','OUT']};tunes=[]
    try:
        with (output/'edges.csv').open() as stream:
            for row in csv.DictReader(stream):events[row['event']].append([float(row['time_ns']),int(row['code']),int(row['bbpd'])])
        with (output/'controls.csv').open() as stream:
            for row in csv.DictReader(stream):
                if row['event']=='ERROR':raise ValueError('model driver error')
                if row['event']=='TUNE':tunes.append([int(row['time_ps'])/1000,int(row['fine'])])
        with (output/'segments.csv').open() as stream:segments=list(csv.DictReader(stream))
        expected=1 if scenario==0 else 2
        if [int(row['segment']) for row in segments]!=list(range(expected)):
            raise ValueError('incomplete or duplicate scenario segments')
        for row in segments:
            start,stop=float(row['enabled_ns']),float(row['stop_ns'])
            if stop-start<220000:raise ValueError('truncated scenario observation')
            r=evaluate(events,tunes,400,start,stop,spec())
            save(output/f'segment{row["segment"]}_acceptance.json',r)
            result['segments'].append(dict(segment=int(row['segment']),passed=r['passed']))
        result['functional_trace_pass']=all(row['passed'] for row in result['segments'])
    except (KeyError,ValueError,OSError,TypeError) as error:
        result['failure']=str(error)
    return result
