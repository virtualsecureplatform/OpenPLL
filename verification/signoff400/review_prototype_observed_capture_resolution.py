"""Measure observed rail-resolution tails without claiming a metastability/FIT bound."""
import argparse
import json
import math
import os
from pathlib import Path
import time
from common_v3 import save,sha,verify
from resources import lease


def resolution(samples,cases,test_ns=20.0,final_start_ns=27.0):
    n=len(cases);last_not_low=[None]*n;last_not_high=[None]*n
    minimum=[math.inf]*n;maximum=[-math.inf]*n;last_time=None;max_step=0.;seen=0
    for row in samples:
        if len(row)!=2+3*n or any(not math.isfinite(x) for x in row):raise ValueError('invalid captured waveform row')
        t=row[0]*1e9
        if last_time is not None:
            if t<=last_time:raise ValueError('capture time is not strictly increasing')
            if t>=test_ns:max_step=max(max_step,t-last_time)
        last_time=t
        if t<test_ns:continue
        for i,v in enumerate(row[2:2+n]):
            if v>=.36:last_not_low[i]=t
            if v<=1.44:last_not_high[i]=t
            if t>=final_start_ns:minimum[i]=min(minimum[i],v);maximum[i]=max(maximum[i],v)
        seen+=1
    if last_time is None or last_time<29.999 or not seen:raise ValueError('capture waveform does not cover the final observation window')
    records=[]
    for i,c in enumerate(cases):
        target=0 if maximum[i]<.36 else 1 if minimum[i]>1.44 else None
        last_bad=last_not_low[i] if target==0 else last_not_high[i]
        bound=None if target is None else max(0.,(last_bad+max_step-test_ns) if last_bad is not None else 0.)
        records.append(dict(**c,observed_final_rail=target,observed_resolution_upper_ns_from_test_edge=bound))
    return records,max_step


def run(capture,output):
    receipt=capture/'assessment.json';authority=json.loads(receipt.read_text());verify(authority['artifacts'])
    paths=[]
    for name,digest in authority['input_sha256'].items():
        p=Path(name)
        if p.name!='assessment.json' or not (p.parent/'waveform.dat').exists():continue
        a=json.loads(p.read_text())
        if a.get('master')=='sky130_fd_sc_hs__dfrtp_1':
            if sha(p)!=digest:raise ValueError('capture point receipt changed')
            paths.append(p)
    if not paths:raise ValueError('native DFRTP1 capture points missing')
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    inputs={str(p):sha(p) for p in (receipt,Path(__file__).resolve())};results=[];maxima={};unresolved=0
    os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    with lease(1,4,deadline):
        for p in paths:
            a=json.loads(p.read_text());verify(a['artifacts'])
            manifest=p.parent/'input_manifest.json';m=json.loads(manifest.read_text());wave=p.parent/'waveform.dat'
            if a['artifacts'].get(str(wave))!=sha(wave):raise ValueError('unbound native waveform')
            with wave.open() as stream:
                header=stream.readline().split()
                if len(header)!=2+3*len(m['cases']) or header[:2]!=['time','v(clk)']:raise ValueError('unexpected native capture columns')
                records,step=resolution((list(map(float,line.split())) for line in stream if line.strip()),m['cases'])
            good=[r['observed_resolution_upper_ns_from_test_edge'] for r in records if r['observed_final_rail'] is not None]
            missing=sum(r['observed_final_rail'] is None for r in records);unresolved+=missing
            if good:maxima[a['corner']]=max(maxima.get(a['corner'],0.),max(good))
            results.append(dict(point=str(p.parent),corner=a['corner'],master=a['master'],load_fF=a['load_fF'],maximum_stored_timestep_ns=step,unresolved_final_rails=missing,records=records))
            inputs.update({str(x):sha(x) for x in (p,manifest,wave)})
    verify(inputs);detail=output/'observed_resolution.json';save(detail,results)
    save(output/'assessment.json',dict(input_sha256=inputs,artifacts={str(detail):sha(detail)},native_points_reviewed=len(paths),native_cases_reviewed=sum(len(p['records']) for p in results),observed_maximum_resolution_ns_by_corner=maxima,unresolved_final_rail_cases=unresolved,old_or_new_final_state_both_allowed=True,continuous_aperture_or_statistical_tail_bound_proved=False,FIT_qualified=False,actual_routed_resolution_budget_compared=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('capture','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.capture.resolve(),a.output.resolve())
