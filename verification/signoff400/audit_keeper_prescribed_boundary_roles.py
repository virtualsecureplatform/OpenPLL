"""Classify prescribed boundary dependencies without changing the conditional circuit."""
import argparse
from collections import Counter
from fractions import Fraction
import json
import os
from pathlib import Path
import time
from common_v3 import ROOT, save, sha, verify
from audit_keeper_DCO_driver_C_cut import capacitance
from native_spice_comments import strip_floating_annotation
from resources import lease

RAILS = {'VPWR','VGND','VPB','VNB','0'}


def inventory(text, interface):
    prescribed=set(interface['externally_driven_ports'])
    observed=set(interface['observation_only_ports'])
    interior=set(interface['interior_nodes']) | observed
    if prescribed & interior:
        raise ValueError('prescribed and unknown nodes must be disjoint')
    roles={n:set() for n in prescribed}
    support={n:Counter() for n in prescribed}
    charge={n:Fraction(0) for n in prescribed}
    names=set()
    for raw in text.splitlines():
        f=strip_floating_annotation(raw).split()
        if not f or f[0][0] not in 'XC':
            continue
        if f[0] in names:
            raise ValueError('unique primitive and capacitor names required')
        names.add(f[0])
        if f[0].startswith('X'):
            end=next((i for i,t in enumerate(f) if '=' in t),len(f))-1
            nodes,model=f[1:end],f[end]
            mos=model.startswith(('sky130_fd_pr__nfet','sky130_fd_pr__pfet'))
            if mos and len(nodes)!=4:
                raise ValueError('four ordered MOS terminals required')
            for i,node in enumerate(nodes):
                if node in roles:
                    role=('MOS_gate' if i==1 else 'MOS_bulk' if i==3 else 'MOS_diffusion') if mos else 'other_primitive_terminal'
                    roles[node].add(role)
                    support[node][role]+=1
        else:
            if len(f)!=4:
                raise ValueError('literal two-terminal capacitance required')
            value=capacitance(f[3])
            if value<0:
                raise ValueError('nonnegative native capacitance required')
            if not value:
                continue
            for node,other in ((f[1],f[2]),(f[2],f[1])):
                if node not in prescribed:
                    continue
                support[node]['capacitors']+=1
                if other in interior:
                    support[node]['capacitors_to_unknowns']+=1
                    charge[node]+=value
                elif other in prescribed or other=='0':
                    support[node]['capacitors_to_prescribed_or_ground']+=1
                else:
                    raise ValueError('capacitor endpoint absent from declared partition')
    rows=[]
    for node in sorted(prescribed):
        if node in RAILS:
            kind='rail'
        elif roles[node]:
            kind='retained_primitive_terminal'
        else:
            kind='capacitive_only'
        rows.append(dict(node=node,kind=kind,terminal_roles=sorted(roles[node]),support=dict(support[node]),
            C_to_unknowns_F_exact=str(charge[node]),
            charge_change_C_per_1V_boundary_change_exact=str(charge[node]),
            charge_coefficient_is_not_frequency_error_bound=True))
    return rows


def run(output):
    output.mkdir(parents=True,exist_ok=False)
    os.sched_setaffinity(0,{19})
    base=ROOT/'build/signoff400'
    source=base/'selected_keeper_receiver_expansion_1416'
    receipt=source/'assessment.json'
    a=json.loads(receipt.read_text())
    verify(a['input_sha256'])
    verify(a['artifacts'])
    model,interface=source/'conditional.spice',source/'interface.json'
    files=[receipt,model,interface,Path(__file__).resolve(),
           Path(__file__).with_name('audit_keeper_DCO_driver_C_cut.py'),
           Path(__file__).with_name('native_spice_comments.py')]
    pins={str(p):sha(p) for p in files}
    with lease(1,2,time.clock_gettime(time.CLOCK_BOOTTIME)+3600):
        rows=inventory(model.read_text(),json.loads(interface.read_text()))
    detail=output/'boundaries.json'
    save(detail,rows)
    verify(pins)
    counts=Counter(r['kind'] for r in rows)
    role_counts=Counter(role for r in rows for role in r['terminal_roles'])
    coupling=sum((Fraction(r['C_to_unknowns_F_exact']) for r in rows if r['kind']=='capacitive_only'),Fraction(0))
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},
         prescribed_boundaries=len(rows),counts_by_kind=dict(counts),boundary_counts_by_terminal_role=dict(role_counts),
         capacitive_only_C_to_unknowns_F_exact=str(coupling),
         circuit_changed=False,independent_environment_supplied=False,
         charge_coefficient_is_not_frequency_error_bound=True,
         changed_controller_prediction_qualified=False,model_qualified=False,release_ready=False))
    save(output/'status.json',dict(state='prescribed_boundary_roles_classified',release_ready=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    run(parser.parse_args().output.resolve())
