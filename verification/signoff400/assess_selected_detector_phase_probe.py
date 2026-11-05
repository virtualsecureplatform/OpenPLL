"""Extract active detector response from a completed conditional native probe.

Response measurements are diagnostic: they do not validate held exterior
voltages, omitted loads, stimulus slews, corner coverage, or a detector fit.
"""
import argparse,csv,json,math
from pathlib import Path
from common_v3 import save,sha,verify
from check_selected_boundary_waveforms import bind


def read_selected(raw,roles,end_time):
    names=[];declared=None;count=None
    with raw.open() as stream:
        for line in stream:
            if line.startswith('No. Variables:'):declared=int(line.split(':',1)[1])
            if line.startswith('No. Points:'):count=int(line.split(':',1)[1])
            if line.strip()=='Variables:':break
        for line in stream:
            if line.strip()=='Values:':break
            index,name,_=line.split()
            if int(index)!=len(names):raise ValueError('invalid variable ordering')
            names.append(name)
        if len(names)!=declared or names[0].lower()!='time' or count is None:raise ValueError('incomplete native header')
        binding=bind(list(dict.fromkeys(roles.values())),names)
        if not binding['all_bound']:raise ValueError('all selected physical voltages must be saved')
        indices={r:binding['bindings'][n]['index'] for r,n in roles.items()};rows=[];previous=-1
        for line in stream:
            if not line.strip():continue
            index,t=line.split();t=float(t)
            if int(index)!=len(rows) or not math.isfinite(t) or t<=previous:raise ValueError('invalid native sample ordering')
            previous=t;values=[t]+[float(next(stream)) for _ in range(declared-1)]
            if not all(math.isfinite(v) for v in values):raise ValueError('nonfinite native voltage')
            rows.append([t]+[values[i] for i in indices.values()])
    if not rows or len(rows)!=count or rows[0][0]!=0 or abs(rows[-1][0]-end_time)>1e-18:raise ValueError('native waveform is truncated')
    return rows


def transitions(rows,column,level=.9):
    rise=[];fall=[]
    for a,b in zip(rows,rows[1:]):
        if (a[column]<level<=b[column]) or (a[column]>=level>b[column]):
            t=a[0]+(level-a[column])/(b[column]-a[column])*(b[0]-a[0])
            (rise if b[column]>a[column] else fall).append(t*1e9)
    return dict(rising_ns=rise,falling_ns=fall)


def run(probe,ports,inventory,output):
    output.mkdir(parents=True,exist_ok=False)
    if json.loads((probe/'status.json').read_text())['state']!='conditional_detector_probe_completed_assessment_pending':raise ValueError('normal native completion required')
    a=json.loads((probe/'assessment.json').read_text());m=json.loads((probe/'manifest.json').read_text())
    verify(a['input_sha256']);verify(a['artifacts'])
    pv=json.loads(ports.read_text());verify(pv['input_sha256'])
    iv=json.loads(inventory.read_text());verify(iv['input_sha256'])
    if pv['input_sha256'].get(str(inventory))!=sha(inventory):raise ValueError('physical pin inventory mismatch')
    model=[p for p in a['input_sha256'] if p.endswith('/model.spice')]
    if len(model)!=1 or iv['input_sha256'].get(model[0])!=a['input_sha256'][model[0]]:raise ValueError('physical pin/model identity mismatch')
    roles=dict(m['observed_roles'])
    roles.update({role+'_pin':pv['ports'][port]['detector_wire_endpoint'] for role,port in [('reference','REF'),('feedback','CLKDIVR'),('detector_reset','RESET_N')]})
    raw=probe/'probe.raw';rows=read_selected(raw,roles,80e-9)
    selected=output/'signals.csv'
    with selected.open('x') as f:
        w=csv.writer(f);w.writerow(['time_s',*roles]);w.writerows(rows)
    result={role:dict(node=node,minimum_V=min(row[i] for row in rows),maximum_V=max(row[i] for row in rows),**transitions(rows,i)) for i,(role,node) in enumerate(roles.items(),1)}
    save(output/'assessment.json',dict(input_sha256={str(p):sha(p) for p in [probe/'assessment.json',probe/'manifest.json',ports,inventory,raw,Path(__file__).resolve(),Path(__file__).with_name('check_selected_boundary_waveforms.py')]},artifacts={str(selected):sha(selected)},
        phase_50_percent_crossing_offset_ns=m['phase_50_percent_crossing_offset_ns'],observations=result,native_samples=len(rows),all_native_samples_finite=True,
        active_phase_response_measured=True,receiver_loading_bounded=False,exterior_condition_validated=False,
        detector_model_qualified=False,release_ready=False))
    print(json.dumps(result))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['probe','ports','inventory','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.probe.resolve(),a.ports.resolve(),a.inventory.resolve(),a.output.resolve())
