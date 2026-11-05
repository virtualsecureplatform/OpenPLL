"""Bind the real feedback driver's input pins for an impedance-retaining bench.

This supplies physical identities and waveform-extraction roles. It does not
clamp the driver Q, construct active detector behavior, or qualify stimuli.
"""
import argparse,json
from pathlib import Path
from common_v3 import save,sha,verify
from compare_prototype_physical_primitive_graphs import parsed
from resolve_prototype_loaded_halo_interfaces import local_bindings


def run(drivers,metadata,wire,hierarchy,output):
    if output.exists():raise FileExistsError(output)
    dv=json.loads(drivers.read_text());verify(dv['input_sha256'])
    for p in [metadata,wire,hierarchy]:
        if dv['input_sha256'].get(str(p))!=sha(p):raise ValueError('same physical driver extraction required')
    driver=dv['clock_drivers']['CLKDIVR'];selected=set(driver['primitives'])
    if driver['master']!='sky130_fd_sc_hs__dfrtp_4' or len(selected)!=39:raise ValueError('complete selected HS DFRTP4 feedback driver required')
    instances=[i for i in json.loads(metadata.read_text())['physical_instances'] if i['instance'] in selected]
    if {i['instance'] for i in instances}!=selected:raise ValueError('feedback driver primitive coverage mismatch')
    key='feedback_driver';cells={n:key for n in selected};terms={}
    for line in wire.open():
        f=line.split()
        if f and f[0] in selected:
            stop=next(i for i,t in enumerate(f) if t.startswith('sky130_fd_pr__'));terms[f[0]]=f[1:stop]
            if len(terms)==len(selected):break
    bound,aliases=local_bindings(instances,terms,cells,parsed(hierarchy.read_text()));entry=bound[key]
    pins={p:entry['nodes'][aliases[entry['master']].find(p)] for p in ['D','CLK','RESET_B','Q','VPWR','VGND','VPB','VNB']}
    if pins['Q']!=driver['node'] or pins['Q'] in [pins[p] for p in ['D','CLK','RESET_B']]:raise ValueError('unique real feedback output and input pins required')
    roles=dict(dv['clock_drivers'])
    for role,pin in [('feedback_ff_clock','CLK'),('feedback_ff_data','D'),('feedback_ff_reset','RESET_B')]:roles[role]=dict(node=pins[pin],master=driver['master'],pin=pin,kind='recorded_driver_input')
    inputs=dict(dv['input_sha256']);inputs.update({str(p):sha(p) for p in [drivers,Path(__file__).resolve()]});verify(inputs)
    save(output,dict(input_sha256=inputs,clock_drivers=roles,feedback_driver=dict(master=entry['master'],primitives=sorted(selected),pins=pins),
        feedback_driver_inputs_bound=True,feedback_driver_Q_must_remain_unknown=True,
        driver_waveforms_qualified=False,active_detector_input_impedance_qualified=False,release_ready=False))
    print(json.dumps(dict(driver_primitives=len(selected),physical_pins=pins,waveform_roles=len(roles))))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['drivers','metadata','wire','hierarchy','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['drivers','metadata','wire','hierarchy','output']))
