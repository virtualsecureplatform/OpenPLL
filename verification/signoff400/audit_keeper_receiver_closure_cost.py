"""Measure monotone native-device closure cost for removing prescribed diffusion outputs."""
from collections import defaultdict
import json
import os
from pathlib import Path
import time
from common_v3 import ROOT, save, sha, verify
from native_spice_comments import strip_floating_annotation
from resources import lease

RAILS={'0','VPWR','VGND','VPB','VNB'}


def graph(text):
    devices={}
    adjacency=defaultdict(set)
    for raw in text.splitlines():
        f=strip_floating_annotation(raw).split()
        if not f or not f[0].startswith('X'):
            continue
        if f[0] in devices:
            raise ValueError('unique primitive names required')
        end=next((i for i,t in enumerate(f) if '=' in t),len(f))-1
        nodes=f[1:end]
        if f[end].startswith(('sky130_fd_pr__nfet','sky130_fd_pr__pfet')):
            if len(nodes)!=4:
                raise ValueError('four ordered MOS terminals required')
            diffusion={nodes[0],nodes[2]}-RAILS
        else:
            diffusion=set(nodes)-RAILS
        devices[f[0]]=diffusion
        for node in set(nodes)-RAILS:
            adjacency[node].add(f[0])
    if not devices:
        raise ValueError('native primitives required')
    return devices,adjacency


def closure(devices,adjacency,selected,limit=20000,max_rounds=32):
    selected=set(selected)
    if not selected or not selected<=devices.keys():
        raise ValueError('existing selected primitive set required')
    rounds=[]
    for index in range(max_rounds):
        front=defaultdict(set)
        for name in selected:
            for node in devices[name]:
                omitted=adjacency[node]-selected
                if omitted:
                    front[node].update(omitted)
        added=set().union(*front.values()) if front else set()
        proposed=selected|added
        rounds.append(dict(round=index,selected_primitives=len(selected),
                           prescribed_diffusion_frontiers=len(front),added_primitives=len(added),
                           proposed_primitives=len(proposed)))
        if not added:
            return dict(rounds=rounds,closure_reached=True,stopped_at_cost_limit=False,
                        required_primitive_lower_bound=len(selected)),selected
        if len(proposed)>limit:
            return dict(rounds=rounds,closure_reached=False,stopped_at_cost_limit=True,
                        required_primitive_lower_bound=len(proposed)),selected
        selected=proposed
    return dict(rounds=rounds,closure_reached=False,stopped_at_cost_limit=False,
                required_primitive_lower_bound=len(selected),round_limit_reached=True),selected


def run():
    base=ROOT/'build/signoff400'
    output=base/'selected_keeper_receiver_closure_cost_1524'
    output.mkdir(parents=True,exist_ok=False)
    os.sched_setaffinity(0,{19})
    source=base/'selected_keeper_flat_geometry_C_1202/capacitance.spice'
    previous=base/'selected_keeper_next_receiver_frontier_1523'
    receipt=previous/'assessment.json'
    a=json.loads(receipt.read_text())
    verify(a['input_sha256'])
    verify(a['artifacts'])
    if a['input_sha256'].get(str(source))!=sha(source):
        raise ValueError('same exact flat source required')
    interface=previous/'interface.json'
    helpers=['native_spice_comments.py']
    files=[source,receipt,interface,Path(__file__).resolve(),*[Path(__file__).with_name(n) for n in helpers]]
    pins={str(p):sha(p) for p in files}
    save(output/'status.json',dict(state='measuring_native_diffusion_closure_cost',release_ready=False))
    with lease(1,8,time.clock_gettime(time.CLOCK_BOOTTIME)+3600):
        devices,adjacency=graph(source.read_text())
        initial=set(json.loads(interface.read_text())['selected_primitive_names'])
        result,selected=closure(devices,adjacency,initial)
    verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={},**result,
         full_flat_primitives=len(devices),initial_primitives=len(initial),
         preparation_limit_primitives=20000,maximum_rounds=32,
         closure_scope='explicit native devices incident to retained nonrail diffusion terminals',
         formal_output_port_reclassification_still_required=True,
         capacitive_exterior_environment_not_closed=True,
         circuit_changed=False,native_cases_added=0,
         independent_prediction_qualified=False,model_qualified=False,release_ready=False))
    save(output/'status.json',dict(state='native_diffusion_closure_cost_measured',release_ready=False))


if __name__=='__main__':
    run()
