#!/usr/bin/env python3
"""Terminal clock-to-Q/assertion observations; no constraint-library qualification."""
from array import array
import math
from pathlib import Path
import time
from characterize_compact_propagation import crossings
from run_dco_qualification import sha,save


def assess(plan,pins,out,deadline):
    def status(state,**fields):save(out/'status.json',dict(state=state,release_qualified=False,**fields))
    def remaining():
        value=deadline-time.clock_gettime(time.CLOCK_BOOTTIME)
        if value<=0:raise TimeoutError('shared timing campaign deadline reached')
        return value
    status('assessing_terminal_native_waveform',native_exit_code=0)
    columns=plan['waveform_columns'];wave=out/'batch.prn';times=array('d');values=[array('d') for _ in columns];terminal=False
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
        artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file() and p.name!='status.json'},fixtures=len(records),
        passing=sum(r['passed'] for r in records),records=records,pvt=plan['pvt'],all_native_waveform_events_terminal=True,
        setup_hold_recovery_removal_qualified=False,physical_timing_qualified=False,
        release_qualified=False,scope=__doc__))
    status('terminal_assessment',fixtures=len(records),passing=sum(r['passed'] for r in records))
    print(f'Sequential propagation terminal: {sum(r["passed"] for r in records)}/{len(records)}',flush=True)

