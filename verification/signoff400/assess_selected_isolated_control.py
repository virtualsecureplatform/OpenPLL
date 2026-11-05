"""Assess a terminal isolated control, including an explicitly partial budget stop.

Never restart or terminate a native job. Compare only a shared measured window;
a budget-limited prefix cannot qualify a model or masquerade as completion.
"""
import argparse,json,math,os,time
from pathlib import Path
from common_v3 import save,sha,verify
from resources import identity
from assess_selected_detector_phase_probe_v2 import transitions
from check_selected_boundary_waveforms import bind


def prefix(raw):
    names=[];declared=None;variables=None;rows=[];truncated=False
    with raw.open() as stream:
        for line in stream:
            if line.startswith('No. Variables:'):variables=int(line.split(':',1)[1])
            if line.startswith('No. Points:'):
                text=line.split(':',1)[1].strip();declared=int(text) if text else None
            if line.strip()=='Variables:':break
        for line in stream:
            if line.strip()=='Values:':break
            index,name,_=line.split()
            if int(index)!=len(names):raise ValueError('invalid RAW variable ordering')
            names.append(name)
        if not names or len(names)!=variables or names[0].lower()!='time':raise ValueError('incomplete native header')
        b=bind(['PLLOUT'],names)
        if not b['all_bound']:raise ValueError('one native oscillator output required')
        output_index=b['bindings']['PLLOUT']['index']
        for line in stream:
            if not line.strip():continue
            if not line.endswith('\n'):truncated=True;break
            index,text=line.split();t=float(text)
            if int(index)!=len(rows) or not math.isfinite(t) or (rows and t<=rows[-1][0]):raise ValueError('invalid sample ordering')
            values=[t]
            for _ in range(variables-1):
                value_line=stream.readline()
                if not value_line or not value_line.endswith('\n'):truncated=True;break
                value=float(value_line)
                if not math.isfinite(value):raise ValueError('nonfinite saved native value')
                values.append(value)
            if truncated:break
            rows.append([t,values[output_index]])
    if not rows or rows[0][0]!=0:raise ValueError('initial complete sample required')
    return rows,dict(declared_points=declared,complete_samples=len(rows),incomplete_final_sample_discarded=truncated,
                     declared_sample_count_complete=declared is not None and declared==len(rows) and not truncated)


def frequency(rows,start,stop):
    edges=[t for t in transitions(rows,1)['rising_ns'] if start<=t<=stop]
    if len(edges)<3:raise ValueError('at least three rises in the common measured window required')
    periods=[b-a for a,b in zip(edges,edges[1:])]
    return dict(rising_edges=len(edges),frequency_mhz=1000/(sum(periods)/len(periods)),minimum_period_ns=min(periods),maximum_period_ns=max(periods))


def run(control,output,wait):
    if output.exists():raise FileExistsError(output)
    owner=json.loads((control/'owner.json').read_text());deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+7200
    while True:
        state=json.loads((control/'status.json').read_text())
        if state['state'] not in ['preparing_isolated_Xyce_control','isolated_Xyce_native_running']:break
        if not wait:raise ValueError('native control is still live; no terminal assessment performed')
        if identity(owner['pid'])!=owner['birth']:raise RuntimeError('controller exited without terminal status')
        if time.clock_gettime(time.CLOCK_BOOTTIME)>deadline:raise TimeoutError('observation deadline exhausted; native job unchanged')
        time.sleep(5)
    full=state['state']=='isolated_backend_frequency_screen_complete'
    budget=state['state']=='stopped_without_qualification' and 'TimeoutError' in state.get('reason','')
    if not full and not budget:raise ValueError('control did not complete normally or stop at its budget: '+str(state))
    process=json.loads((control/'native.process.json').read_text())
    if identity(process['pid'])==process['birth']:raise ValueError('native worker still live; terminal inspection required')
    manifest=control/'manifest.json';m=json.loads(manifest.read_text());verify(m['input_sha256'])
    raw=control/'control.raw';rows,info=prefix(raw)
    if full and (not info['declared_sample_count_complete'] or abs(rows[-1][0]-40e-9)>1e-18):raise ValueError('normal completion without complete 40 ns waveform')
    stop=min(40.0,rows[-1][0]*1e9);ng=[Path(p) for p in m['input_sha256'] if p.endswith('.waveform.tsv')]
    if len(ng)!=1:raise ValueError('one pinned ngspice reference waveform required')
    reference=[]
    for line in ng[0].open():
        t,v=map(float,line.split())
        if not math.isfinite(t) or not math.isfinite(v):raise ValueError('nonfinite reference voltage')
        if t<=stop*1e-9:reference.append([t,v])
    x=frequency(rows,20,stop);n=frequency(reference,20,stop)
    output.mkdir(parents=True)
    save(output/'assessment.json',dict(input_sha256={str(p):sha(p) for p in [manifest,control/'status.json',raw,ng[0],Path(__file__).resolve(),Path(__file__).with_name('assess_selected_detector_phase_probe_v2.py')]},
        normal_full_window_completed=full,native_budget_stopped=budget,native_circuit_failure_demonstrated=False,
        waveform=info,common_measured_window_ns=[20,stop],Xyce=x,ngspice=n,
        frequency_difference_ppm=1e6*(x['frequency_mhz']/n['frequency_mhz']-1),
        numerical_convergence_qualified=False,fast_model_qualified=False,physical_models_qualified=False,release_ready=False))
    print(json.dumps(dict(normal_full_window_completed=full,budget_stopped=budget,common_window_ns=[20,stop],Xyce=x,ngspice=n)))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--control',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--wait',action='store_true')
    a=p.parse_args();os.sched_setaffinity(0,{30});run(a.control.resolve(),a.output.resolve(),a.wait)
