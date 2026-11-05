#!/usr/bin/env python3
"""Correlate DCO signal terminals and SPEF R coordinates with actual macro GDS.

Use independently transformed actual-instance LEF probes to identify each net's
physical conductor component. Preserve finite poly resistors. Require every
SPEF point to touch its expected component; coordinate metadata lacks layer
identity, so this does not qualify distributed capacitor placement.
"""
from collections import defaultdict
import copy
import json
import math
from pathlib import Path
import signal
import sys
import time
import pya
from audit_DCO_intercell_wire_rc import normalized,canonical
from correlate_digital_pin_capacitance_geometry_v2 import validate
from device_aware_conductor_geometry import conductor_geometry
from check_forming_antenna_geometry_v2 import engine_at_stage
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT,sha,save


def main():
    base=ROOT/'build/timing400/release_001'
    source=base/'current_DCO_intercell_wire_rc_001';inventory=base/'DCO_signal_pin_geometry_001'
    i=verify(inventory/'assessment.json');assert i['exact_def_gds_instance_transforms'] and i['signal_terminals']==2071
    wire_audit=base/'DCO_intercell_wire_rc_audit_001/assessment.json';assert verify(wire_audit)['all_multiterminal_DEF_nets_covered']
    control=base/'tie_resistor_geometry_controls_001/assessment.json';assert verify(control)['hi_vpwr_and_lo_vgnd_separated']
    topname='IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160'
    gds=ROOT/f'openlane/{topname}/runs/c1fine_range_001/final/gds/{topname}.gds'
    assert sha(gds)==i['input_sha256'][str(gds)]
    owner_path=base/'candidate_layout_checks_001/owner.json'
    left=json.loads(owner_path.read_text())['deadline_uptime']-time.clock_gettime(time.CLOCK_BOOTTIME)
    assert left>0;signal.alarm(max(1,math.floor(left)))
    rows=json.loads((inventory/'terminals.json').read_text())
    layout=pya.Layout();layout.read(str(gds));assert layout.dbu==.001
    top=layout.cell(topname);assert top is not None
    engine,regs=engine_at_stage(conductor_geometry(layout,top),'m5')
    resolved=[];missing_rectangles=0
    for row in rows:
        clusters=set();missing=[]
        for probe in row['probes']:
            node=engine.probe_net(regs[probe['layer']],pya.Point(*probe['point_nm']))
            if node is None:missing.append(probe)
            else:clusters.add(node.cluster_id)
        missing_rectangles+=len(missing)
        result={k:v for k,v in row.items() if k!='probes'}
        result.update(clusters=sorted(clusters),missing_rectangular_probes=len(missing))
        resolved.append(result)
    logical,physical=validate(resolved,{})
    assert len(logical)==956
    labels={net:next(iter(ids)) for net,ids in logical.items()}
    records=[];unmatched=[]
    for corner in ['min','nom','max']:
        for net,row in normalized(source/f'{corner}.spef').items():
            assert net in labels
            for node,xy in row['coordinates'].items():
                point=[round(x*1000) for x in xy];matches=[]
                for kind in ['li','m1','m2','m3','m4','m5']:
                    found=engine.probe_net(regs[kind],pya.Point(*point))
                    if found is not None:matches.append(dict(layer=kind,cluster=found.cluster_id))
                passed=labels[net] in {r['cluster'] for r in matches}
                result=dict(corner=corner,net=net,spef_node=node,point_nm=point,
                    expected_cluster=labels[net],physical_matches=matches,expected_net_found=passed)
                records.append(result)
                if not passed:unmatched.append(result)
    wrong=copy.deepcopy(resolved)
    first=next(i for i,r in enumerate(wrong) if r['logical_net'] is not None)
    other=next(r for r in wrong if r['logical_net'] not in [None,wrong[first]['logical_net']])
    wrong[first]['clusters']=other['clusters']
    try:validate(wrong,{})
    except AssertionError:pass
    else:raise AssertionError('wrong terminal geometry projection accepted')
    out=base/'DCO_intercell_wire_rc_geometry_001';out.mkdir(exist_ok=False)
    save(out/'terminals.json',resolved);save(out/'coordinates.json',records);save(out/'unmatched.json',unmatched)
    paths=[Path(__file__).resolve(),Path(sys.executable),inventory/'assessment.json',inventory/'terminals.json',
        wire_audit,control,owner_path,gds,Path(__file__).with_name('device_aware_conductor_geometry.py'),
        Path(__file__).with_name('check_forming_antenna_geometry_v2.py'),
        Path(__file__).with_name('correlate_digital_pin_capacitance_geometry_v2.py'),
        Path(__file__).with_name('audit_DCO_intercell_wire_rc.py'),*[source/f'{c}.spef' for c in ['min','nom','max']]]
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in paths},
        artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()},
        components_matched_to_DEF_and_GDS=i['components'],signal_terminals_correlated=len(resolved),logical_nets_correlated=956,
        unrouted_body_only_public_ports_without_signal_terminals=["VPB","VNB"],
        missing_or_split_signal_terminals=0,distinct_logical_nets_shorted=0,
        missing_rectangular_probes_retained=missing_rectangles,
        RC_coordinates_checked=len(records),RC_coordinates_on_expected_net=len(records)-len(unmatched),
        unmatched_RC_coordinates=len(unmatched),all_RC_coordinates_correlated=not unmatched,
        wrong_terminal_projection_negative_control_rejected=True,
        finite_poly_resistor_bodies_not_ideal_shorts=True,expected_conductor_membership_only=True,
        unique_SPEF_layer_identity_qualified=False,C_to_R_distribution_qualified=False,
        complete_cell_internal_R_qualified=False,full_RC_enclosure_qualified=False,
        physical_timing_qualified=False,release_qualified=False,adopted=False,scope=__doc__))
    print('DCO physical correlation:',len(resolved),'terminals,',len(records),'RC coordinates;',len(unmatched),'unmatched.')


if __name__=='__main__':main()
