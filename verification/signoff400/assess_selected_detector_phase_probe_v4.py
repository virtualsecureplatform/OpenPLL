"""Assess a completed conditional detector probe, preserving printed-time collisions.

Response measurements are diagnostic: they do not validate held exterior
voltages, omitted loads, stimulus slews, corner coverage, or a detector fit.
"""
import argparse,csv,json,math
from pathlib import Path
from common_v3 import save,sha,verify
from check_selected_boundary_waveforms import bind


def read_selected(raw,roles,end_time):
    from assess_selected_detector_prefix import read_prefix
    rows,info=read_prefix(raw,roles)
    if info['incomplete_final_sample_discarded'] or info['declared_samples']!=len(rows) or abs(rows[-1][0]-end_time)>1e-18:
        raise ValueError('normal completion requires every declared sample through the endpoint')
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
    optional={role+'_pin':pv['ports'][port]['detector_wire_endpoint'] for role,port in [('reference','REF'),('feedback','CLKDIVR'),('detector_reset','RESET_N')]}
    raw=probe/'probe.raw';names=[]
    with raw.open() as stream:
        for line in stream:
            if line.strip()=='Variables:':break
        for line in stream:
            if line.strip()=='Values:':break
            names.append(line.split()[1])
    available=bind(list(optional.values()),names)
    missing=[role for role,node in optional.items() if node not in available['bindings']]
    roles.update({role:node for role,node in optional.items() if node in available['bindings']})
    duration=m.get('native_duration_ns',80)
    if duration not in [80,90]:raise ValueError('declared 80 or 90 ns detector protocol required')
    rows=read_selected(raw,roles,duration*1e-9)
    selected=output/'signals.csv'
    with selected.open('x') as f:
        w=csv.writer(f);w.writerow(['time_s',*roles]);w.writerows(rows)
    result={role:dict(node=node,minimum_V=min(row[i] for row in rows),maximum_V=max(row[i] for row in rows),**transitions(rows,i)) for i,(role,node) in enumerate(roles.items(),1)}
    save(output/'assessment.json',dict(input_sha256={str(p):sha(p) for p in [probe/'assessment.json',probe/'manifest.json',ports,inventory,raw,Path(__file__).resolve(),Path(__file__).with_name('check_selected_boundary_waveforms.py'),Path(__file__).with_name('assess_selected_detector_prefix.py')]},artifacts={str(selected):sha(selected)},
        native_duration_ns=duration,first_reference_target_ns=m.get('first_reference_target_ns',20),
        repeated_printed_timestamps=sum(a[0]==b[0] for a,b in zip(rows,rows[1:])),
        native_time_order='nondecreasing printed timestamps; every complete sample retained',
        phase_50_percent_crossing_offset_ns=m['phase_50_percent_crossing_offset_ns'],observations=result,native_samples=len(rows),all_native_samples_finite=True,
        active_phase_response_measured=True,missing_physical_input_observations=missing,physical_input_slews_measured=not missing,receiver_loading_bounded=False,exterior_condition_validated=False,
        detector_model_qualified=False,release_ready=False))
    print(json.dumps(result))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['probe','ports','inventory','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.probe.resolve(),a.ports.resolve(),a.inventory.resolve(),a.output.resolve())
