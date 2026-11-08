"""Finish the device-closure cost study without exporting or simulating the large circuit."""
import json
import os
from pathlib import Path
import time
from common_v3 import ROOT, save, sha, verify
from resources import lease
from audit_keeper_receiver_closure_cost import graph,closure


def run():
    base=ROOT/'build/signoff400'
    output=base/'selected_keeper_full_receiver_closure_1525'
    output.mkdir(parents=True,exist_ok=False)
    os.sched_setaffinity(0,{19})
    previous=base/'selected_keeper_next_receiver_frontier_1523'
    study=base/'selected_keeper_receiver_closure_cost_1524/assessment.json'
    source=base/'selected_keeper_flat_geometry_C_1202/capacitance.spice'
    receipt=previous/'assessment.json'
    a,b=[json.loads(p.read_text()) for p in (receipt,study)]
    for record in (a,b):
        verify(record['input_sha256'])
        verify(record['artifacts'])
    if a['input_sha256'].get(str(source))!=sha(source):
        raise ValueError('same original native source required')
    interface=previous/'interface.json'
    files=[receipt,study,source,interface,Path(__file__).resolve(),
           Path(__file__).with_name('audit_keeper_receiver_closure_cost.py'),
           Path(__file__).with_name('native_spice_comments.py')]
    pins={str(p):sha(p) for p in files}
    save(output/'status.json',dict(state='measuring_full_native_receiver_closure',release_ready=False))
    with lease(1,8,time.clock_gettime(time.CLOCK_BOOTTIME)+3600):
        devices,adjacency=graph(source.read_text())
        initial=set(json.loads(interface.read_text())['selected_primitive_names'])
        result,selected=closure(devices,adjacency,initial,limit=len(devices),max_rounds=256)
    selected_file=output/'selected_primitive_names.json'
    save(selected_file,sorted(selected))
    verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(selected_file):sha(selected_file)},
         **result,initial_primitives=len(initial),full_flat_primitives=len(devices),
         retained_fraction=len(selected)/len(devices),maximum_rounds=256,
         circuit_exported=False,native_cases_added=0,
         closure_scope='explicit native devices incident to retained nonrail diffusion terminals',
         formal_output_port_reclassification_still_required=True,
         capacitive_exterior_environment_not_closed=True,
         independent_prediction_qualified=False,model_qualified=False,release_ready=False))
    save(output/'status.json',dict(state='full_native_receiver_closure_cost_measured',release_ready=False))


if __name__=='__main__':
    run()
