#!/usr/bin/env python3
"""Bind external-protection parent route, full DRC and unique LVS to one GDS.

Both repaired source macros and the original oscillator must be preserved;
Original and targeted diode and well-tap placements must match the physical placement plan.
Signal routes were rebuilt. Density, antenna, RC, noise, timing and analog
qualification remain separate mandatory gates.
"""
import argparse
import json
from pathlib import Path
from check_compact_clock_tree import verify
from run_dco_qualification import sha,save


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['route','stream','layout','lvs','output']:parser.add_argument('--'+name,required=True,type=Path)
    parser.add_argument('--filled',action='store_true')
    args=parser.parse_args();route,stream,layout,lvs,out=[getattr(args,n).resolve() for n in ['route','stream','layout','lvs','output']]
    r=verify(route/'assessment.json');s=verify(stream/'assessment.json');e=verify(layout/'native_completion.json');v=verify(lvs/'assessment.json')
    assert r['router_drc_violations']==0 and r['main_rail_connectivity_passed'] and r['parent_signal_routes_rebuilt']
    assert s['all_source_macro_geometry_and_labels_preserved'] and s['missing_cells']==0
    if args.filled:
        assert s['only_new_metal5_fill_replaced'] and s['all_original_parent_geometry_and_labels_preserved']
    assert s['parent_diode_instances']==564 and s['parent_well_tap_instances']==141 and s['external_physical_cell_placements_match_plan']
    assert e['drc_and_extraction_native_completed'] and v['assembled_lvs_passed'] and v['all_three_macros_expanded']
    gds=stream/'assembly.gds';spice=layout/'assembly.spice'
    assert sha(gds)==s['artifacts'][str(gds)]==e['input_sha256'][str(gds)]
    assert sha(spice)==e['artifacts'][str(spice)]==v['input_sha256'][str(spice)]
    assert e['input_sha256'][str(route/'route.odb')]==sha(route/'route.odb')
    assert sha(route/'powered_top.v')==sha(layout/'powered_top.v')==v['input_sha256'][str(layout/'powered_top.v')]
    assert (layout/'drc_errors.rpt').read_text().strip()=='MAGIC_DRC_RECTANGLES=0'
    log=(layout/'drc.log').read_text();recipe=(layout/'drc.tcl').read_text()
    assert 'No errors found.' in log and 'MAGIC_DRC_RECTANGLES=0' in log
    assert 'drc style drc(full)' in recipe and f'gds read {gds}' in recipe
    assert all(word not in log for word in ['Input off lambda grid','snapped to grid','Error:'])
    data=json.loads((lvs/'compare.json').read_text());top='IntegerPLL_400MHz_CandidateTop'
    assert data[-1]['name']==[top,top] and data[-1]['nets'][0]==data[-1]['nets'][1]
    assert all(not row.get('badnets') and not row.get('badelements') for row in data)
    pins=data[-1]['pins'];assert len(pins)==2 and len(pins[0])==len(pins[1])==55 and set(pins[0])==set(pins[1])
    assert (lvs/'compare.log').read_text().rstrip().endswith('Final result: Circuits match uniquely.\n.')
    owners=[json.loads((p/'owner.json').read_text()) for p in [layout,lvs]]
    assert owners[0]['deadline_uptime']==owners[1]['deadline_uptime']
    for owner in owners:
        p=Path('/proc')/str(owner['runner_pid'])
        assert not p.exists() or (p/'stat').read_text().rsplit(')',1)[1].split()[0]=='Z'
    files=[Path(__file__).resolve(),route/'assessment.json',stream/'assessment.json',layout/'native_completion.json',layout/'drc.tcl',
        layout/'drc.log',layout/'drc_errors.rpt',lvs/'assessment.json',lvs/'compare.json',lvs/'compare.log']
    out.mkdir(parents=True,exist_ok=False)
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in files},artifacts={},
        assembled_gds=str(gds),assembled_gds_sha256=sha(gds),routed_database=str(route/'route.odb'),routed_database_sha256=sha(route/'route.odb'),
        magic_drc_rectangles=0,assembled_magic_drc_passed=True,assembled_lvs_passed=True,all_three_macros_expanded=True,top_pins=55,
        macro_geometry_and_labels_preserved=True,parent_diode_instances=564,parent_well_tap_instances=141,
        parent_signal_routes_rebuilt=True,no_magic_input_geometry_snapping=True,shared_original_layout_deadline=True,
        filled=args.filled,routed_database_includes_fill=False,fill_aware_electrical_extraction_required=args.filled,density_qualified=False,antenna_qualified=False,rc_qualified=False,em_ir_qualified=False,
        physical_noise_qualified=False,physical_timing_qualified=False,release_qualified=False,adopted=False,scope=__doc__))
    print('Exact external-protection GDS passes full DRC0 and unique LVS; all3 macros,564diodes,141taps and55pins bound. Other release gates remain open.')

if __name__=='__main__':main()
