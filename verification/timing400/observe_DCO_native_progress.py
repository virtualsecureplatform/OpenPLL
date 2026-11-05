#!/usr/bin/env python3
"""Observe one identified native DCO without restarting or changing its inputs.

Frequency and runtime projections are provisional startup observations only.
"""
import argparse
from datetime import datetime,timezone
import json,math,os
from pathlib import Path
import time
from compile_local_C_operators_v2 import digest,save
from record_qualification_progress_045 import process

parser=argparse.ArgumentParser();parser.add_argument('--point',type=Path,required=True)
parser.add_argument('--native-pid',type=int,required=True);parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args();point=args.point.resolve();out=args.output.resolve()
owner=json.loads((point/'owner.json').read_text());deadline=owner['deadline_uptime']
identity=process(args.native_pid);assert identity['live'] and identity['argv'][-1]==str(point/'point.cir')
assert json.loads((point/'status.json').read_text())['native_pid']==args.native_pid
out.mkdir(exist_ok=False)
save(out/'owner.json',dict(runner_pid=os.getpid(),native_identity=identity,
    started_utc=datetime.now(timezone.utc).isoformat(),deadline_uptime=deadline,
    native_input_changed=False,native_process_started_or_retried=False))
pins={str(p.resolve()):digest(p) for p in [Path(__file__),point/'owner.json',point/'input_manifest.json']}
save(out/'input_manifest.json',dict(input_sha256=pins))
wave=Path(str(point/'point.cir')+'.prn');offset=0;pending=b'';header=False;terminal=False
count=0;previous=None;minimum=None;maximum=None;risings=[];fallings=[];history=[]
reset_end=5.05e-9;target=80e-9

def read_new_rows():
    global offset,pending,header,terminal,count,previous,minimum,maximum
    if not wave.exists():return
    assert wave.stat().st_size>=offset,'source waveform was truncated'
    with wave.open('rb') as handle:handle.seek(offset);data=handle.read();offset=handle.tell()
    parts=(pending+data).split(b'\n');pending=parts.pop()
    for raw in parts:
        line=raw.decode();fields=line.split()
        if not fields:continue
        if not header:
            assert fields==['Index','TIME','V(PLLOUT)','I(VVPWR)'];header=True;continue
        if 'End of Xyce(TM) Simulation' in line:assert not terminal;terminal=True;continue
        assert not terminal and len(fields)==4 and int(fields[0])==count
        row=tuple(float(v) for v in fields[1:]);assert all(math.isfinite(v) for v in row)
        assert (previous is None and row[0]==0) or (previous is not None and row[0]>previous[0])
        minimum=row[1] if minimum is None else min(minimum,row[1])
        maximum=row[1] if maximum is None else max(maximum,row[1])
        if previous is not None:
            rising=previous[1]<.9<=row[1];falling=previous[1]>.9>=row[1]
            if rising or falling:
                edge=previous[0]+(.9-previous[1])*(row[0]-previous[0])/(row[1]-previous[1])
                if edge>=reset_end:(risings if rising else fallings).append(edge)
        previous=row;count+=1

def snapshot(live):
    now=time.clock_gettime(time.CLOCK_BOOTTIME);simulation=previous[0] if previous else 0.
    # Allow a rate projection only after three complete post-reset periods.
    projected=None;span=None
    if len(risings)>=4:
        eligible=[h for h in history if h['uptime']>=now-900 and h['simulation_time_s']>=risings[0]]
        if eligible and now-eligible[0]['uptime']>=300:
            first=eligible[0];span=now-first['uptime'];advance=simulation-first['simulation_time_s']
            if advance>0:projected=now+max(0,target-simulation)*span/advance
    frequency=(len(risings[-5:])-1)/(risings[-1]-risings[-5:][0])*1e-6 if len(risings)>=2 else None
    result=dict(observed_utc=datetime.now(timezone.utc).isoformat(),uptime=now,
        observer_pid=os.getpid(),source_native_pid=args.native_pid,source_native_live=live,
        samples=count,simulation_time_s=simulation,terminal_wave_marker_seen=terminal,
        output_min_V=minimum,output_max_V=maximum,post_reset_rising_edges=len(risings),
        post_reset_falling_edges=len(fallings),startup_frequency_last_four_periods_MHz=frequency,
        post_reset_rising_edge_times_s=risings[-128:],
        observed_rate_projection_finish_uptime=projected,projection_observation_s=span,
        projection_within_remaining_budget=None if projected is None else projected<=deadline,
        runtime_projection_is_provisional=True,settled_frequency_qualified=False,
        native_case_verdict_not_inferred=True,release_qualified=False,adopted=False)
    history.append(result)
    with (out/'observations.jsonl').open('a') as handle:handle.write(json.dumps(result)+'\n')
    save(out/'status.json',result)
    return result

try:
    while True:
        current=process(args.native_pid);live=current['live'] and current['argv']==identity['argv']
        read_new_rows();result=snapshot(live)
        if not live or time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:break
        time.sleep(min(30,max(.01,deadline-time.clock_gettime(time.CLOCK_BOOTTIME))))
    save(out/'assessment.json',dict(observation_finished=True,last_observation=result,input_sha256=pins,
        source_native_restarted=False,source_native_inputs_changed=False,
        source_native_completion_not_inferred=True,release_qualified=False,adopted=False))
except Exception as error:
    save(out/'observer_failure.json',dict(error_type=type(error).__name__,message=str(error),
        native_process_changed=False,release_qualified=False));raise
