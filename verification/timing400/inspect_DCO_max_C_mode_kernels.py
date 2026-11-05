#!/usr/bin/env python3
"""Locate the largest failed-mode ground terms in the owned max-C native trace."""
from collections import Counter
import json
import os
from pathlib import Path
import signal
import time
from compile_local_C_operators_v2 import digest,save
from verify_magic_C_owners import owned_blocks


def main():
    base=Path(__file__).resolve().parents[2]/'build/timing400/release_001'
    owner=base/'distributed_RC_model_qualification_001/owner.json'
    deadline=json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME)<deadline
    signal.alarm(max(1,int(deadline-time.clock_gettime(time.CLOCK_BOOTTIME))))
    energy=base/'DCO_max_C_mode_energy_trace_001'
    proof=energy/'assessment.json'
    assert json.loads(proof.read_text())['negative_energy_mode_reconstruction_passed']
    negative=energy/'largest_negative_operators.json'
    selected=[r for r in json.loads(negative.read_text()) if r['operator'][2]==0][:20]
    wanted={r['operator'][3] for r in selected}
    assert all(n>0 for n in wanted)
    trace=base/'DCO_C_owner_trace_max_001/max_trace'
    out=base/'DCO_max_C_mode_kernel_inspection_001'
    out.mkdir(exist_ok=False)
    found=[]
    for count,(block,ownership) in enumerate(owned_blocks(trace,deadline),1):
        matches=[e for e in block['events'] if int(e[1]) in wanted]
        if matches:
            found.append(dict(matching_event_serials=[int(e[1]) for e in matches],
                ownership=ownership,kernel=block,selected_operators=[r for r in selected
                    if r['operator'][3] in {int(e[1]) for e in matches}]))
        if count%10000==0:
            save(out/'status.json',dict(state='inspecting_owned_maximum_C_kernels',
                runner_pid=os.getpid(),kernels_checked=count,selected_found=len(found),deadline_uptime=deadline))
    assert wanted=={n for r in found for n in r['matching_event_serials']}
    save(out/'selected_kernels.json',found)
    kinds=Counter(r['kernel']['kind'] for r in found)
    inputs=[Path(__file__).resolve(),owner,proof,negative,trace/'kernels.log',trace/'owners.log',
        trace/'node_ids.json',base/'DCO_local_C_operators_max_self_001/assessment.json']
    save(out/'assessment.json',dict(selected_largest_negative_ground_operators=len(selected),
        selected_native_event_count=len(wanted),selected_kernel_kinds=dict(kinds),
        explicit_same_conductor_owners=sum(bool(r['ownership'] and r['ownership']['same_ideal_conductor']) for r in found),
        model_changed=False,runtime_model_eligible=False,release_qualified=False,adopted=False,deadline_uptime=deadline,
        input_sha256={str(p.resolve()):digest(p) for p in inputs},
        artifacts={str((out/'selected_kernels.json').resolve()):digest(out/'selected_kernels.json')}))
    save(out/'status.json',dict(state='completed',selected_kernel_kinds=dict(kinds)))
    print(json.dumps(dict(kinds=kinds,selected_events=len(wanted))))


if __name__=='__main__':main()
