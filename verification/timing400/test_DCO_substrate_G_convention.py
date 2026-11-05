#!/usr/bin/env python3
"""Test omission of the native-discarded substrate-node G accumulator.

Remove all positive and negative native G operators whose original conductor
is the native substrate. Keep every explicit inter/intra-conductor pair term.
The native .ext substrate record always writes zero C; its internal G sum is
unobservable after ideal-conductor collapse. This is a model-convention
experiment, not proof of a physical finite-R return or an adopted correction.
"""
import argparse
from collections import Counter,defaultdict
import json
import os
from pathlib import Path
import shlex
import signal
import time
import numpy as np
from scipy.sparse import coo_matrix,diags,load_npz,save_npz
from assemble_local_C_matrix import Atlas,integrate_operator
from compile_local_C_operators_v2 import digest,save


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--corner',choices=['min','nom','max'],required=True)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[2]
    base=root/'build/timing400/release_001'
    owner=base/'distributed_RC_model_qualification_001/owner.json'
    deadline=json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME)<deadline
    signal.alarm(max(1,int(deadline-time.clock_gettime(time.CLOCK_BOOTTIME))))
    corner=args.corner
    trace=base/('DCO_C_owner_trace_001/nom_trace' if corner=='nom' else f'DCO_C_owner_trace_{corner}_001/{corner}_trace')
    extraction=next(trace.glob('IntegerPLL*.ext'))
    substrate=[shlex.split(line) for line in extraction.read_text().splitlines() if line.startswith('substrate ')]
    assert len(substrate)==1 and substrate[0][1]=='VGND' and substrate[0][2:4]==['0','0']
    native_source=root/'build/timing400/magic_C_owner_source_001/extract/ExtBasic.c'
    assert r'fprintf(outFile, "substrate \"%s\" 0 0", text);' in native_source.read_text()
    mapping=json.loads((trace/'node_ids.json').read_text())
    assert list(mapping.values()).count('@SUBSTRATE')==1
    family=base/'DCO_complete_domain_model_primitives_001'
    operators=base/('DCO_local_C_operators_nom_self_002' if corner=='nom' else f'DCO_local_C_operators_{corner}_self_001')
    old=base/f'DCO_local_C_matrix_{corner}_self_001'
    old_proof=json.loads((old/'assessment.json').read_text())
    names=json.loads((old/'nodes.json').read_text())
    assert names[0]=='_dco_substrate_reference'
    index={n:i for i,n in enumerate(names)}
    original={r['private_id']:r['original_conductor'] for r in json.loads((family/'nodes.json').read_text())}
    fields=json.loads((operators/'fields.json').read_text())
    atlas=Atlas(family/'voltage_domains.jsonl',fields)
    out=base/f'DCO_local_C_matrix_{corner}_no_substrate_G_001'
    out.mkdir(exist_ok=False)
    counts=Counter()
    upper=defaultdict(float)
    def status(state):
        save(out/'status.json',dict(state=state,runner_pid=os.getpid(),counts=dict(counts),deadline_uptime=deadline))
    status('assembling_native_discarded_substrate_G_component')
    size=len(names)
    for row_text in (operators/'operators.jsonl').open():
        row=json.loads(row_text)
        counts['operators_scanned']+=1
        if row[2]==0 and fields[row[1]][0]=='VGND':
            assert row[3]>0 and row[0] in ['A','L']
            counts['excluded_substrate_G_operators']+=1
            counts['excluded_'+row[0]]+=1
            for local in integrate_operator(atlas,row):
                for (a,b),value in local.items():
                    assert a=='_dco_substrate_reference' or original[a]=='VGND'
                    assert b=='_dco_substrate_reference' or original[b]=='VGND'
                    ia,ib=sorted([index[a],index[b]])
                    upper[ia*size+ib]+=value
        if counts['operators_scanned']%50000==0:
            assert time.clock_gettime(time.CLOCK_BOOTTIME)<deadline
            status('assembling_native_discarded_substrate_G_component')
    assert counts['operators_scanned']==json.loads((operators/'assessment.json').read_text())['counts']['operators']
    encoded=np.fromiter(upper.keys(),dtype=np.int64,count=len(upper))
    values=np.fromiter(upper.values(),dtype=np.float64,count=len(upper))
    triangular=coo_matrix((values,(encoded//size,encoded%size)),shape=(size,size)).tocsr()
    component=triangular+triangular.T-diags(triangular.diagonal())
    # All component vertices collapse to the SAME native substrate conductor.
    # Its only collapsed entry is the total sum, which must vanish numerically.
    collapsed_error=abs(float(component.sum()))
    absolute_sum=float(abs(component).sum())
    assert collapsed_error<=1e-12*absolute_sum
    candidate=load_npz(old/'C_native_units.npz').tocsr()-component
    row_scale=np.asarray(abs(candidate).sum(axis=1)).ravel()
    relative=abs(np.asarray(candidate.sum(axis=1)).ravel())/np.maximum(row_scale,1e-30)
    assert max(relative)<1e-10,float(max(relative))
    save_npz(out/'excluded_substrate_G_native_units.npz',component)
    save_npz(out/'C_native_units.npz',candidate)
    save(out/'nodes.json',names)
    inputs=[Path(__file__).resolve(),owner,native_source,extraction,trace/'node_ids.json',
        operators/'fields.json',operators/'operators.jsonl',operators/'assessment.json',
        old/'assessment.json',old/'nodes.json',old/'C_native_units.npz',family/'nodes.json',family/'voltage_domains.jsonl',
        Path(__file__).with_name('assemble_local_C_matrix.py'),Path(__file__).with_name('local_C_field_integrals.py')]
    result=dict(full_nominal_C_energy_matrix_assembled=corner=='nom',full_C_energy_matrix_assembled=True,
        RC_corner=corner,counts=dict(counts),explicit_substrate_reference_vertex=True,
        native_private_voltage_vertices=len(names)-1,matrix_nonzeros=candidate.nnz,capacitance_unit_F=1e-18,
        native_substrate_G_convention_experiment=True,native_substrate_output_capacitance_zero_verified=True,
        both_positive_and_negative_substrate_G_operators_omitted=True,all_explicit_pair_operators_preserved=True,
        ideal_conductor_collapse_change_native_units=collapsed_error,
        maximum_relative_charge_row_residual=float(max(relative)),signed_global_passivity_qualified=False,
        physical_return_geometry_or_finite_R_error_bound_qualified=False,
        runtime_model_eligible=False,release_qualified=False,adopted=False,deadline_uptime=deadline,
        input_sha256={str(p.resolve()):digest(p) for p in inputs},
        artifacts={str(p.resolve()):digest(p) for p in [out/'excluded_substrate_G_native_units.npz',out/'C_native_units.npz',out/'nodes.json']})
    save(out/'assessment.json',result)
    status('completed_convention_experiment_passivity_pending')
    print(json.dumps({k:v for k,v in result.items() if k not in ['input_sha256','artifacts']},indent=2))


if __name__=='__main__':main()
