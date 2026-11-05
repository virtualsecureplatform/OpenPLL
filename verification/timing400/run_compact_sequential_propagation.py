#!/usr/bin/env python3
"""Run a prepared sequential propagation batch once, within a total12h budget.

Waits for terminal passing combinational fixtures and shared native capacity.
Produces raw clock-to-Q, asynchronous assertion delay and output-slew data.
No setup/hold/recovery/removal, MTBF or timing-library qualification is claimed.
"""
import argparse
from datetime import datetime,timezone
import json
import math
import os
from pathlib import Path
import subprocess
import time

from characterize_compact_propagation import XYCE,admit_one,crossings
from check_compact_clock_tree import verify
from run_dco_qualification import sha,save


def main():
    started=time.monotonic();deadline=started+43200
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('plan','after','output'):parser.add_argument('--'+key,required=True,type=Path)
    args=parser.parse_args();plan_path=args.plan.resolve();after=args.after.resolve();out=args.output.resolve()
    plan=json.loads(plan_path.read_text());out.mkdir(parents=True,exist_ok=False)
    claim=plan_path.parent/'native_run.json'
    with claim.open('x') as stream:
        json.dump(dict(runner_pid=os.getpid(),output=str(out),after=str(after),
                       launched_utc=datetime.now(timezone.utc).isoformat(),automatic_identical_retry=False),stream,indent=2)
    pins={str(plan_path):sha(plan_path),str(Path(__file__).resolve()):sha(Path(__file__).resolve()),
          str(Path(__file__).with_name('characterize_compact_propagation.py').resolve()):sha(Path(__file__).with_name('characterize_compact_propagation.py')),
          **plan['input_sha256']}
    def status(state,**fields):
        save(out/'status.json',dict(observed_utc=datetime.now(timezone.utc).isoformat(),state=state,
             per_check_total_budget_s=43200,release_qualified=False,**fields))
    def remaining():
        value=deadline-time.monotonic()
        if value<=0:
            status('timeout_inconclusive');raise TimeoutError('total check budget reached')
        return value
    status('waiting_for_terminal_combinational_assessment',prerequisite=str(after))
    while not after.exists():time.sleep(min(30,remaining()))
    prerequisite=verify(after)
    if prerequisite['passing']!=prerequisite['fixtures'] or not prerequisite['all_native_waveform_events_terminal']:
        status('prerequisite_nonpass_no_native_launch');return
    pins[str(after)]=sha(after)
    for path,digest in pins.items():assert sha(Path(path))==digest,path
    while True:
        remaining()
        try:admit_one(out);break
        except AssertionError as error:
            status('waiting_for_native_capacity',reason=str(error));time.sleep(min(30,remaining()))
    deck=plan_path.parent/'batch.cir'
    command=[str(XYCE),'-linsolv','KLU','-quiet','-o',str(out/'batch'),str(deck)]
    with (out/'run.log').open('x') as stream:
        child=subprocess.Popen(command,stdout=stream,stderr=subprocess.STDOUT)
        save(out/'launch.json',dict(pid=child.pid,command=command,input_sha256=pins,
                                  total_budget_s=43200,release_qualified=False))
        status('native_running',native_pid=child.pid)
        try:code=child.wait(timeout=remaining())
        except subprocess.TimeoutExpired:
            child.terminate()
            try:child.wait(timeout=30)
            except subprocess.TimeoutExpired:child.kill();child.wait()
            status('timeout_inconclusive',native_pid=child.pid);return
    assert code==0,(out/'run.log').read_text()[-2000:]
    status('assessing_terminal_native_waveform',native_exit_code=code)
    columns=plan['waveform_columns'];wave=out/'batch.prn';times=[];values=[[] for _ in columns];terminal=False
    with wave.open() as stream:
        assert stream.readline().split()==['Index','TIME',*columns]
        for line in stream:
            if 'End of Xyce(TM) Simulation' in line:terminal=True;continue
            row=line.split()
            if not row:continue
            assert row[0].isdigit() and int(row[0])==len(times)
            numbers=list(map(float,row));assert len(numbers)==len(columns)+2 and all(map(math.isfinite,numbers))
            times.append(numbers[1])
            for series,value in zip(values,numbers[2:]):series.append(value)
            if len(times)%1000==0:remaining()
    assert terminal and times[0]==0 and times[-1]>=plan['stop_ns']*1e-9-1e-15
    assert all(a<b for a,b in zip(times,times[1:]))
    records=[]
    for i,case in enumerate(plan['fixtures']):
        remaining();clk,data,reset,output=values[4*i:4*i+4]
        record=dict(case_index=i,passed=False,output_min_v=min(output),output_max_v=max(output))
        try:
            assert abs(reset[0])<1e-6 and abs(clk[0])<1e-6
            assert (output[0]>=1.62 if case['reset_value'] else output[0]<=.18)
            assert min(output)<.18 and max(output)>1.62
            clock_edges=crossings(times,clk,.9,True);assert len(clock_edges)==4
            out_edges={direction:crossings(times,output,.9,direction) for direction in (False,True)}
            transitions={direction:[] for direction in (False,True)}
            previous=case['reset_value']
            for index,t in enumerate(clock_edges):
                target=case['expected_captured_values'][index]
                if case['kind']=='async_assert':previous=case['reset_value']
                assert target!=previous
                rising=target>previous
                selected=[u for u in out_edges[rising] if t-1e-9<u<t+5e-9]
                assert len(selected)==1
                transitions[rising].append(selected[0]);previous=target
                record.setdefault('clock_to_q_rise_ns' if rising else 'clock_to_q_fall_ns',[]).append((selected[0]-t)*1e9)
            if case['kind']=='clock_toggle':assert all(len(out_edges[d])==2 for d in (False,True))
            else:
                rising=bool(case['reset_value'])
                starts=crossings(times,reset,.9,False);assert len(starts)==3
                assert len(out_edges[rising])==3 and len(out_edges[not rising])==4
                for t in starts:
                    selected=[u for u in out_edges[rising] if t-1e-9<u<t+5e-9];assert len(selected)==1
                    transitions[rising].append(selected[0])
                    record.setdefault('assertion_to_q_ns',[]).append((selected[0]-t)*1e9)
            for rising,centers in transitions.items():
                if not centers:continue
                first=crossings(times,output,.36 if rising else 1.44,rising)
                last=crossings(times,output,1.44 if rising else .36,rising)
                slews=[]
                for center in centers:
                    left=[t for t in first if center-5e-9<t<=center]
                    right=[t for t in last if center<=t<center+5e-9]
                    assert left and right
                    slew=(min(right)-max(left))*1e9;assert slew>0;slews.append(slew)
                record['output_rise_20_80_ns' if rising else 'output_fall_80_20_ns']=slews
            record['passed']=True
        except AssertionError:record['reason']='DC rail, event/state or threshold correspondence failed'
        records.append(record)
    for path,digest in pins.items():assert sha(Path(path))==digest,path
    remaining()
    save(out/'assessment.json',dict(input_sha256=pins,
        artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()},fixtures=len(records),
        passing=sum(r['passed'] for r in records),records=records,all_native_waveform_events_terminal=True,
        setup_hold_recovery_removal_qualified=False,physical_timing_qualified=False,
        release_qualified=False,scope=__doc__))
    status('terminal_assessment',fixtures=len(records),passing=sum(r['passed'] for r in records))
    print(f'Sequential propagation terminal: {sum(r["passed"] for r in records)}/{len(records)}',flush=True)


if __name__=='__main__':main()
