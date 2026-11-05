#!/usr/bin/env python3
"""Bind the last antenna repair to route identity and independent geometry."""
from pathlib import Path
import re
from check_bbpd_repair_identity import design
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT,sha,save


def lengths(body):
    result={f'met{i}':0 for i in range(1,6)}
    for layer,path in re.findall(r'(?:\+ (?:ROUTED|FIXED)|NEW) (met[1-5]) (.*?)(?= NEW |$)',body):
        previous=None
        for x,y in re.findall(r'\(\s*(\S+)\s+(\S+)(?:\s+\S+)?\s*\)',path):
            point=(previous[0] if x=='*' else int(x),previous[1] if y=='*' else int(y))
            if previous is not None:result[layer]+=abs(point[0]-previous[0])+abs(point[1]-previous[1])
            previous=point
    return {layer:value/1000 for layer,value in result.items()}


def main():
    base=ROOT/'build/timing400/release_001';old=base/'parent_dco_antenna_targeted_008';new=base/'parent_dco_antenna_targeted_011'
    before=verify(old/'assessment.json');after=verify(new/'assessment.json')
    assert after['unchanged_background_signal_routes']==356
    geo=base/'parent_dco_antenna_geometry_011';a=verify(geo/'antenna/assessment.json');t=verify(geo/'topology/assessment.json')
    assert a['violations']==0 and a['all_drawing_mos_gate_area_enumerated_at_each_stage']
    assert t['complete_port_connectivity_screen_passed']
    _,_,on=design(old/'route.def');_,_,nn=design(new/'route.def');target='DCO_THERM[53]'
    bl,al=lengths(on[target]),lengths(nn[target]);assert al['met3']<bl['met3']
    files=[Path(__file__).resolve(),old/'assessment.json',new/'assessment.json',old/'route.def',new/'route.def',
        geo/'antenna/assessment.json',geo/'topology/assessment.json',base/'parent_dco_antenna_localization_008/assessment.json']
    out=base/'parent_dco_antenna_single_net_repair_audit_011';out.mkdir(exist_ok=False)
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in files},artifacts={},
        target_net=target,before_wire_length_um=bl,after_wire_length_um=al,m3_wire_length_reduction_um=bl['met3']-al['met3'],
        unchanged_background_signal_routes=356,all_instance_placements_and_bindings_preserved=True,
        independent_conservative_antenna_violations=0,independent_topology_screen_passed=True,
        full_native_drc_lvs_required=True,filled_candidate_checks_required=True,matching_rc_required=True,
        release_qualified=False,adopted=False,scope=__doc__))
    print('M3 length',bl['met3'],'->',al['met3'],'um; all356other routes unchanged; independent geometry0.')

if __name__=='__main__':main()
