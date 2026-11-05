#!/usr/bin/env python3
"""Check native bulk-node material claims against independent actual-GDS wells.

The DCO has no deep nwell. Treat default substrate inside its GDS bounding box
outside drawn nwell as pwell, as specified by the retained PDK substrate rule.
Verify the34 previously unresolved ground junctions, and inventory all MOS-body
node support outcomes. Material membership is not an impedance, R magnitude,
junction allocation or transient-error bound.
"""
from collections import defaultdict,Counter
from pathlib import Path
import json,math,signal,sys,time
import pya
from audit_active_dco_rc_capacitance import parse,terminals
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT,sha,save


def main():
    base=ROOT/'build/timing400/release_001';proof=base/'DCO_R_node_provenance_inspection_002/assessment.json'
    a=verify(proof);assert a['native_node_coordinate_multiset_exactly_recovered']
    assert a['ground34_origin_flags']=={'junction':34} and a['ground34_material_names']==['pwell']
    source=base/'DCO_R_node_trace_controls_002/trace'
    topname='IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160'
    gds=ROOT/f'openlane/{topname}/runs/c1fine_range_001/final/gds/{topname}.gds'
    tech=ROOT/'build/timing450/pdk/sky130A/libs.tech/magic/sky130A.tech'
    assert sha(gds)=='0f227ae41fa996eaa23410aecbe7a3b38090185285c768ba24435026f337a2dd'
    rule='substrate *ppdiff,*mvppdiff,space/w,pwell well $SUB -dnwell,isosub'
    assert rule in tech.read_text()
    owner=base/'candidate_layout_checks_001/owner.json';deadline=json.loads(owner.read_text())['deadline_uptime']
    left=deadline-time.clock_gettime(time.CLOCK_BOOTTIME);assert left>0;signal.alarm(max(1,math.floor(left)))
    layout=pya.Layout();layout.read(str(gds));assert layout.dbu==.001;top=layout.cell(topname)
    def region(layer,datatype):return pya.Region(top.begin_shapes_rec(layout.layer(layer,datatype))).merged()
    nw=region(64,20);dnw=region(64,18);assert dnw.is_empty(),'deep-well material requires a separate qualified interpretation'
    bbox=top.bbox();pw=pya.Region(bbox)-nw
    def memberships(point):
        x,y=point;probe=pya.Region(pya.Box(x-1,y-1,x+1,y+1))
        # Full2nm square coverage avoids declaring an interface point unique.
        return [name for name,r in [('pwell',pw),('nwell',nw)] if (r&probe).area()==4]
    grounds=json.loads((proof.parent/'ground_internal_metadata.json').read_text());ground_rows=[]
    for r in grounds:
        found=memberships(r['point_nm']);assert found==['pwell'],(r['name'],r['point_nm'],found)
        ground_rows.append(dict(**r,actual_GDS_materials=found,independent_well_mask_support_passed=True))
    assert len(ground_rows)==34
    nodes=json.loads((proof.parent/'node_metadata.json').read_text());models=parse(source/(topname+'.rcx.spice'))
    body=defaultdict(set)
    for row in models['X'].values():
        if terminals(row)!=4:continue
        body[row[3]].add('pwell' if '__nfet_' in row[4] else 'nwell' if '__pfet_' in row[4] else 'unknown')
    assert all(len(v)==1 and 'unknown' not in v for v in body.values())
    bodies=[];stats=Counter()
    for r in nodes:
        if r['name'] not in body:continue
        expected=next(iter(body[r['name']]));found=memberships(r['point_nm']);passed=found==[expected]
        stats['matched_expected_well' if passed else 'unresolved_or_outside_expected_well']+=1
        bodies.append(dict(**r,expected_MOS_body_material=expected,actual_GDS_materials=found,expected_well_support=passed))
    assert bodies
    # A pwell claim deliberately moved into a drawn nwell must fail.
    wrong=None
    for polygon in nw.each():
        center=polygon.bbox().center()
        if memberships([center.x,center.y])==['nwell']:wrong=[center.x,center.y];break
    assert wrong is not None and memberships(wrong)!=['pwell']
    outside=[bbox.right+1000000,bbox.top+1000000];assert memberships(outside)==[]
    out=base/'DCO_bulk_material_support_001';out.mkdir(exist_ok=False)
    save(out/'ground34.json',ground_rows);save(out/'MOS_body_supports.json',bodies)
    save(out/'unresolved_body_supports.json',[r for r in bodies if not r['expected_well_support']])
    paths=[Path(__file__).resolve(),Path(sys.executable),proof,proof.parent/'ground_internal_metadata.json',proof.parent/'node_metadata.json',
        source/(topname+'.rcx.spice'),gds,tech,owner,Path(__file__).with_name('audit_active_dco_rc_capacitance.py')]
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in paths},artifacts={str(p):sha(p) for p in out.iterdir()},
        actual_GDS_ground34_pwell_junction_membership_passed=True,drawn_deep_nwell_absent=True,
        pwell_definition='GDS bounding box minus drawn nwell, under the pinned PDK substrate rule',
        support_probe_square_nm=2,ground_junction_records_checked=34,MOS_body_coordinate_records=len(bodies),
        MOS_body_material_classification=dict(stats),all_MOS_body_record_wells_matched=all(r['expected_well_support'] for r in bodies),
        wrong_well_and_outside_domain_controls_rejected=True,bulk_well_R_magnitudes_or_impedance_qualified=False,
        C_and_junction_distribution_or_transient_error_qualified=False,release_qualified=False,adopted=False,scope=__doc__))
    print('Bulk material support: all34 ground junctions in actual implicit pwell; MOS-body records',dict(stats),'; impedance remains unqualified.')


if __name__=='__main__':main()
