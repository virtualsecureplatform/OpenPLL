"""Add physical synchronizer/reset traces to an existing driver inventory.

These are capture roles, not permissions to prescribe observed outputs or to
substitute inactive reset traces for an active detector test protocol.
"""
import argparse,json
from pathlib import Path
from common_v3 import save,sha,verify


def run(base,stimuli,output):
    if output.exists():raise FileExistsError(output)
    b,s=[json.loads(p.read_text()) for p in [base,stimuli]]
    verify(b['input_sha256']);verify(s['input_sha256'])
    shared={p:d for p,d in s['input_sha256'].items() if p in b['input_sha256']}
    if len(shared)<3 or any(b['input_sha256'][p]!=d for p,d in shared.items()):raise ValueError('same physical stimulus/driver inventory required')
    roles=dict(b['clock_drivers'])
    for role in ['synchronizer_clock','synchronizer_reset_n','event_reset_n','detector_reset_n']:
        node=s['prescribed_voltage_roles'][role]
        if node in {r['node'] for r in roles.values()}:raise ValueError('capture roles unexpectedly alias another driver input')
        roles[role]=dict(node=node,kind='recorded_physical_interface_voltage')
    pins=dict(b['input_sha256']);pins.update({str(p):sha(p) for p in [base,stimuli,Path(__file__).resolve()]});verify(pins)
    save(output,dict(input_sha256=pins,clock_drivers=roles,feedback_driver=b['feedback_driver'],
        synchronizer_clock_native_waveform_requested=True,active_reset_protocol_qualified=False,
        driver_waveforms_qualified=False,release_ready=False))
    print(json.dumps(dict(waveform_roles=len(roles),synchronizer_clock_node=roles['synchronizer_clock']['node'])))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['base','stimuli','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['base','stimuli','output']))
