#!/usr/bin/env python3
"""Transfer existing nominal floating-node energy bounds using exact matrix deltas.

For each target, Dirichlet energy is minimized over floating potentials. Both
positive capacitor networks admit minimizers in[0,1]. A changed floating-edge
weight delta therefore changes the minimum by an amount between min(delta,0)
and max(delta,0). Boundary/boundary energies are known exactly. Sum these bounds
and the prior certified interval; no new linear solve or floating grounding.
The original zero-wire-R, fixed-other-boundary and no-nonlinear-charge scope is
retained. This is a parsed-network load certificate, not runtime qualification.
"""
from collections import defaultdict
from datetime import datetime,timezone
from decimal import Decimal,localcontext,ROUND_FLOOR,ROUND_CEILING
from pathlib import Path
import hashlib,json,math,signal,time
from check_bbpd_repair_identity import design
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT,sha,save


def device_nodes(path):
    nodes=set();cards=0
    for line in path.open():
        if line.startswith('C'):
            assert cards==100462;break
        if not line or line[0] not in 'MDRX':continue
        f=line.split();kind=f[0][0]
        if kind=='X':
            indices=[i for i,v in enumerate(f) if v.startswith('sky130_fd_pr__')]
            assert len(indices)==1 and indices[0] in [3,5];n=indices[0]-1
        else:n=4 if kind=='M' else 2
        nodes.update(f[1:n+1]);cards+=1
    assert cards==100462 and len(nodes)==33669
    return nodes


def main():
    base=ROOT/'build/timing400/release_001'
    old_path=base/'floating_capacitance_reduction_001/assessment.json';old=verify(old_path)
    assert old['all_requested_width_targets_met'] and old['floating_nodes_eliminated_by_zero_incremental_charge_kcl']
    difference=base/'RC_substrate_C_context_matrix_difference_001/nom/assessment.json';change=verify(difference)
    nominal=base/'RC_substrate_capacitance_collection_002/nom/positive/assessment.json';new=verify(nominal)
    before=next(Path(p) for p in old['input_sha256'] if p.endswith('capacitance_positive.spice'))
    after=nominal.parent/'capacitance_positive.spice'
    assert device_nodes(before)==device_nodes(after)
    route=base/'parent_dco_antenna_targeted_011/route.def';_,_,nets=design(route);assert len(nets)==359
    targets=[r['target'] for r in old['targets']]
    boundary=device_nodes(after)|set(nets)|{'0','VGND','VPWR','VSUBS'}|set(targets)
    assert len(boundary)==old['graph']['declared_boundaries']==33673
    owner_path=base/'candidate_layout_checks_001/owner.json';deadline=json.loads(owner_path.read_text())['deadline_uptime']
    left=deadline-time.clock_gettime(time.CLOCK_BOOTTIME);assert left>0;signal.alarm(max(1,math.floor(left)))
    exact=defaultdict(Decimal);negative=Decimal(0);positive=Decimal(0);floating=[];nonself=0
    rows= difference.parent/'pair_differences.jsonl'
    with localcontext() as ctx:
        ctx.prec=80
        for line in rows.open():
            row=json.loads(line);a,b=row['nodes'];delta=Decimal(row['delta_ff'])
            if a==b:continue
            nonself+=1
            if a in boundary and b in boundary:
                for target in targets:
                    if target in [a,b]:exact[target]+=delta
            else:
                negative+=min(delta,Decimal(0));positive+=max(delta,Decimal(0));floating.append(row)
        assert nonself==change['changed_nonself_energy_pairs']
        results=[]
        for row in old['targets']:
            name=row['target'];lower=Decimal.from_float(row['wire_capacitance_lower_ff']);upper=Decimal.from_float(row['wire_capacitance_upper_ff'])
            lower=(lower+exact[name]+negative).quantize(Decimal('1e-12'),rounding=ROUND_FLOOR)
            upper=(upper+exact[name]+positive).quantize(Decimal('1e-12'),rounding=ROUND_CEILING)
            assert lower>=0 and upper>=lower
            results.append(dict(target=name,wire_capacitance_lower_ff=str(lower),wire_capacitance_upper_ff=str(upper),
                interval_width_ff=str(upper-lower),exact_boundary_energy_shift_ff=str(exact[name]),
                floating_perturbation_lower_ff=str(negative),floating_perturbation_upper_ff=str(positive),
                relative_interval_width_ppm=str((upper-lower)/lower*Decimal('1e6'))))
        # Actual formula controls on a two-capacitor series network.
        for delta in [Decimal(4),Decimal(-1)]:
            before_toy=Decimal(2)*Decimal(3)/Decimal(5)
            after_toy=Decimal(2)*(Decimal(3)+delta)/(Decimal(5)+delta)
            assert before_toy+min(delta,Decimal(0))<=after_toy<=before_toy+max(delta,Decimal(0))
    out=base/'RC_substrate_floating_capacitance_bounds_001';out.mkdir(exist_ok=False)
    save(out/'target_bounds.json',results);save(out/'changed_floating_edges.json',floating)
    paths=[Path(__file__).resolve(),old_path,difference,rows,nominal,before,after,route,owner_path,
        Path(__file__).with_name('check_bbpd_repair_identity.py')]
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in paths},artifacts={str(p):sha(p) for p in out.iterdir()},
        original_floating_certificate_verified=True,same_actual_device_node_and_boundary_sets_proven=True,
        declared_boundaries=len(boundary),changed_nonself_pairs=nonself,changed_floating_edges=len(floating),
        exact_Decimal_matrix_deltas_used=True,maximum_principle_energy_perturbation_enclosure_applied=True,
        prior_solver_or_native_CAD_repeated=False,floating_nodes_not_grounded_as_an_approximation=True,
        positive_and_negative_series_network_controls_passed=True,targets=results,
        diagnostic_assumptions=old['diagnostic_assumptions'],actual_FOM_material_or_distributed_RC_qualified=False,
        nonlinear_device_charge_included=False,physical_timing_qualified=False,model_adopted=False,release_qualified=False,scope=__doc__))
    print('RC-substrate nominal wire-C bounds transferred without re-solving:',results)


if __name__=='__main__':main()
