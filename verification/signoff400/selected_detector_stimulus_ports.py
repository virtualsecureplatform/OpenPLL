"""Declare voltage-input cuts for a conditional detector phase bench.

Pin identity is physical; input waveforms and their independence still require
qualification. Detector/event/synchronizer output nodes must remain unknowns.
"""
import argparse,json
from pathlib import Path
from common_v3 import save,sha,verify


def declarations(ports,receivers):
    drives={role:ports['ports'][port]['outside_wire_endpoint']
            for role,port in [('reference','REF'),('feedback','CLKDIVR'),('detector_reset_n','RESET_N')]}
    observed={role:ports['ports'][port]['detector_wire_endpoint']
              for role,port in [('detector_up','BBPD[1]'),('detector_dn','BBPD[0]')]}
    event=[c for c in receivers['selected_cells'] if 'D' in c['pins'] and 'CLK' in c['pins']]
    if len(event)!=2:raise ValueError('two event receivers required')
    resets={c['pins']['RESET_B'] for c in event}
    if len(resets)!=1:raise ValueError('event reset domains differ')
    drives['event_reset_n']=resets.pop()
    for i,c in enumerate(event):observed[f'event{i}']=c['pins']['Q']
    downstream=[c for cells in receivers['downstream_sequential_output_cells'].values() for c in cells]
    if len(downstream)!=2:raise ValueError('two synchronizer loads required')
    for pin,role in [('CLK','synchronizer_clock'),('RESET_B','synchronizer_reset_n')]:
        nodes={c['pins'][pin] for c in downstream}
        if len(nodes)!=1:raise ValueError('synchronizer input domains differ')
        drives[role]=nodes.pop()
    for i,c in enumerate(downstream):observed[f'synchronizer{i}']=c['pins']['Q']
    if set(drives.values())&set(observed.values()):raise ValueError('voltage cut would clamp a detector or receiver output')
    if len(set(drives.values()))!=len(drives):raise ValueError('independent drive roles share a physical node')
    return drives,observed


def run(ports,receivers,output,clock_drivers=None):
    if output.exists():raise FileExistsError(output)
    pv,rv=[json.loads(p.read_text()) for p in [ports,receivers]]
    verify(pv['input_sha256']);verify(rv['input_sha256'])
    if rv['input_sha256'].get(str(ports))!=sha(ports):raise ValueError('receiver port identity mismatch')
    pins={str(p):sha(p) for p in [ports,receivers,Path(__file__).resolve()]}
    drives,observed=declarations(pv,rv)
    if clock_drivers is not None:
        cv=json.loads(clock_drivers.read_text());verify(cv['input_sha256'])
        if cv['input_sha256'].get(str(ports))!=sha(ports) or cv['input_sha256'].get(str(receivers))!=sha(receivers):
            raise ValueError('clock driver physical identity mismatch')
        for role,port in [('reference','REF'),('feedback','CLKDIVR')]:
            drives[role]=cv['clock_drivers'][port]['node']
        if set(drives.values())&set(observed.values()):raise ValueError('output voltage clamp forbidden')
        pins[str(clock_drivers)]=sha(clock_drivers)
    verify(pins);save(output,dict(input_sha256=pins,prescribed_voltage_roles=drives,observed_unknown_roles=observed,
        physical_pin_identity_bound=True,independent_voltage_stimuli_qualified=False,
        waveform_shapes_qualified=False,receiver_loading_bounded=False,release_ready=False))
    return drives


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['ports','receivers','output']:p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--clock-drivers',type=Path)
    a=p.parse_args();print(json.dumps(run(a.ports.resolve(),a.receivers.resolve(),a.output.resolve(),a.clock_drivers.resolve() if a.clock_drivers else None)))
