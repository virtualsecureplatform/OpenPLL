#!/usr/bin/env python3
"""Verify the four remaining body-record coordinates are declared power origins.

Match each logged metal4/5 supply origin to the same independently connected
GDS conductor as its actual top-level power-port label. Internal body locations
stay governed by the preceding well-mask check. A supply boundary coordinate
is not substituted for a physical MOS body location; lumped body connections
and junction allocation still need physical qualification.
"""
from pathlib import Path
import json,math,signal,sys,time
import pya
from audit_active_dco_rc_capacitance import parse
from device_aware_conductor_geometry import conductor_geometry
from check_forming_antenna_geometry_v2 import engine_at_stage
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT,sha,save


def main():
    base=ROOT/'build/timing400/release_001';proof=base/'DCO_bulk_material_support_001/assessment.json'
    p=verify(proof);assert p['actual_GDS_ground34_pwell_junction_membership_passed']
    assert p['MOS_body_material_classification']=={'unresolved_or_outside_expected_well':4,'matched_expected_well':8204}
    rows=json.loads((proof.parent/'unresolved_body_supports.json').read_text())
    source=base/'DCO_R_node_trace_controls_002/trace'
    topname='IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160'
    model=parse(source/(topname+'.rcx.spice'))
    gds=ROOT/f'openlane/{topname}/runs/c1fine_range_001/final/gds/{topname}.gds'
    assert sha(gds)=='0f227ae41fa996eaa23410aecbe7a3b38090185285c768ba24435026f337a2dd'
    owner=base/'candidate_layout_checks_001/owner.json';deadline=json.loads(owner.read_text())['deadline_uptime']
    left=deadline-time.clock_gettime(time.CLOCK_BOOTTIME);assert left>0;signal.alarm(max(1,math.floor(left)))
    layout=pya.Layout();layout.read(str(gds));assert layout.dbu==.001;top=layout.cell(topname)
    engine,regs=engine_at_stage(conductor_geometry(layout,top),'m5')
    ports={};port_rows=[]
    for kind,layer in [('m4',71),('m5',72)]:
        for shape in top.shapes(layout.layer(layer,5)).each():
            if not shape.is_text() or shape.text.string not in ['VGND','VPWR']:continue
            name=shape.text.string;point=shape.text.trans.disp
            found=engine.probe_net(regs[kind],point);assert found is not None
            assert (name,kind) not in ports;ports[name,kind]=found.cluster_id
            port_rows.append(dict(port=name,layer=kind,point_nm=[point.x,point.y],cluster=found.cluster_id))
    assert len(ports)==4 and all(ports[name,'m4']==ports[name,'m5'] for name in ['VGND','VPWR'])
    assert ports['VGND','m4']!=ports['VPWR','m4']
    verified=[]
    for row in rows:
        assert row['name'] in model['ports'] and row['name'] in ['VGND','VPWR']
        assert row['why']==8 and row['origin_flags']==['origin']
        materials=row['incident_material_counts'];assert len(materials)==1
        material=next(iter(materials));assert material in ['metal4','metal5'] and materials[material]==1
        kind='m'+material[-1];point=row['point_nm'];found=set()
        for dx,dy in [(0,0),(1,1),(-1,1),(1,-1),(-1,-1)]:
            net=engine.probe_net(regs[kind],pya.Point(point[0]+dx,point[1]+dy))
            if net is not None:found.add(net.cluster_id)
        expected=ports[row['name'],kind];assert found=={expected},(row['name'],kind,point,found)
        verified.append(dict(**row,actual_power_port_conductor=expected,matched_layer=kind,
            supply_origin_conductor_membership_passed=True))
    assert len(verified)==4
    wrong=ports['VPWR','m4'];assert wrong!=ports['VGND','m4']
    out=base/'DCO_bulk_supply_origin_support_001';out.mkdir(exist_ok=False)
    save(out/'power_ports.json',port_rows);save(out/'supply_origins.json',verified)
    paths=[Path(__file__).resolve(),Path(sys.executable),proof,proof.parent/'unresolved_body_supports.json',
        source/(topname+'.rcx.spice'),gds,owner,Path(__file__).with_name('device_aware_conductor_geometry.py'),
        Path(__file__).with_name('check_forming_antenna_geometry_v2.py'),Path(__file__).with_name('audit_active_dco_rc_capacitance.py')]
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in paths},artifacts={str(p):sha(p) for p in out.iterdir()},
        supply_origin_records_checked=4,all_supply_origin_records_on_actual_declared_port_conductor=True,
        metal4_and_metal5_power_ports_connected_per_rail=True,power_and_ground_not_shorted=True,
        prior_internal_body_well_material_records=8204,prior_ground_junction_pwell_records=34,
        actual_internal_bulk_material_membership_explained=True,
        power_origin_coordinates_are_physical_MOS_body_locations=False,
        lumped_body_connections_at_supply_origins_or_bulk_impedance_qualified=False,
        physical_C_junction_allocation_or_transient_error_qualified=False,release_qualified=False,adopted=False,scope=__doc__))
    print('All4 supply-origin records match actual M4/M5 power-port conductors;8204 internal body positions and34 ground pwell junctions accounted for. Body/junction/impedance qualification remains open.')


if __name__=='__main__':main()
