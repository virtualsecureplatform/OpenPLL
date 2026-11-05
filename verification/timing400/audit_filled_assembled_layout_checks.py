#!/usr/bin/env python3
"""Bind filled assembled Magic DRC, complete LVS and PDK density to one GDS.

This closes these geometry/connectivity checks only. Antenna, density, EM/IR,
noise, timing and physical behavioral qualification remain separate gates.
"""
import argparse
import json
from pathlib import Path
import re

from check_compact_clock_tree import verify
from run_dco_qualification import ROOT,sha,save


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('layout','lvs','stream','repair','output'):
        parser.add_argument('--'+name,required=True,type=Path)
    args=parser.parse_args()
    layout,lvs,stream,repair,out=(getattr(args,k).resolve() for k in ('layout','lvs','stream','repair','output'))
    assert not out.exists()
    extraction=verify(layout/'native_completion.json')
    comparison=verify(lvs/'assessment.json')
    streamed=verify(stream/'assessment.json')
    fixed=verify(repair/'assessment.json')
    assert extraction['drc_and_extraction_native_completed']
    assert comparison['assembled_lvs_passed'] and comparison['all_three_macros_expanded']
    assert streamed['all_source_macro_geometry_and_labels_preserved'] and streamed['missing_cells']==0
    assert fixed['ordinary_signal_def_routes_unchanged'] and fixed['main_rail_connectivity_passed']
    geometry=verify(ROOT/'build/timing400/release_001/candidate_drc_density_filled_002/assessment.json')
    assert geometry['pdk_density_checks_passed']==175 and geometry['pdk_density_checks_failed']==0
    assert streamed['all_added_fill_vertices_on_5nm_grid']
    gds=stream/'assembly.gds'
    assert geometry['assembled_gds']==str(gds) and geometry['assembled_gds_sha256']==sha(gds)
    assert sha(gds)==streamed['artifacts'][str(gds)]==extraction['input_sha256'][str(gds)]
    spice=layout/'assembly.spice'
    assert sha(spice)==extraction['artifacts'][str(spice)]==comparison['input_sha256'][str(spice)]
    assert extraction['input_sha256'][str(repair/'route.odb')]==sha(repair/'route.odb')
    recipe=(layout/'drc.tcl').read_text()
    assert 'drc style drc(full)' in recipe and f'gds read {gds}' in recipe
    drc=(layout/'drc_errors.rpt').read_text()
    assert re.findall(r'MAGIC_DRC_RECTANGLES=(\d+)',drc)==['0']
    assert drc.strip()=='MAGIC_DRC_RECTANGLES=0'
    log=(layout/'drc.log').read_text()
    assert 'No errors found.' in log and 'MAGIC_DRC_RECTANGLES=0' in log
    assert 'Input off lambda grid' not in log and 'snapped to grid' not in log
    assert 'Error:' not in log
    data=json.loads((lvs/'compare.json').read_text())
    top='IntegerPLL_400MHz_CandidateTop'
    assert data[-1]['name']==[top,top]
    assert data[-1]['nets'][0]==data[-1]['nets'][1]
    assert all(not r.get('badnets') and not r.get('badelements') for r in data)
    pins=data[-1]['pins'];assert len(pins)==2
    assert len(pins[0])==len(pins[1])==55 and set(pins[0])==set(pins[1])
    assert (lvs/'compare.log').read_text().rstrip().endswith('Final result: Circuits match uniquely.\n.')
    plan=json.loads((repair/'repair_plan.json').read_text())
    assert all(all(v%5==0 for v in row[1:]) for row in plan['metal5_rectangles'])
    assert json.loads((repair/'metal5_width_preflight.json').read_text())['error_pairs']==0
    owners=[json.loads((d/'owner.json').read_text()) for d in (layout,lvs)]
    assert owners[0]['deadline_uptime']==owners[1]['deadline_uptime']
    for owner in owners:assert not (Path('/proc')/str(owner['runner_pid'])).exists()
    # Retained real failures ensure the verification flow is not green-only.
    base=ROOT/'build/timing400/release_001'
    negative=verify(base/'candidate_lvs_001/assessment.json')
    assert not negative['assembled_lvs_passed']
    old_drc=(base/'candidate_layout_checks_001/drc_errors.rpt').read_text()
    assert re.findall(r'MAGIC_DRC_RECTANGLES=(\d+)',old_drc)==['256']
    files=[ROOT/'build/timing400/release_001/candidate_drc_density_filled_002/assessment.json',Path(__file__).resolve(),layout/'native_completion.json',layout/'drc_errors.rpt',
           layout/'drc.log',layout/'drc.tcl',lvs/'assessment.json',lvs/'compare.json',
           lvs/'compare.log',stream/'assessment.json',repair/'assessment.json',
           base/'candidate_lvs_001/assessment.json',base/'candidate_layout_checks_001/drc_errors.rpt']
    out.mkdir(parents=True)
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in files},
        assembled_gds=str(gds),assembled_gds_sha256=sha(gds),
        routed_database=str(repair/'route.odb'),routed_database_sha256=sha(repair/'route.odb'),
        magic_drc_style='drc(full)',magic_drc_rectangles=0,assembled_magic_drc_passed=True,
        assembled_lvs_passed=True,all_three_macros_expanded=True,top_pins=55,
        macro_geometry_and_labels_preserved=True,ordinary_signal_routes_unchanged=True,
        generated_power_routing_on_5nm_grid=True,no_magic_input_geometry_snapping=True,
        retained_bad_power_grid_rejected=True,shared_original_12h_deadline=True,
        added_fill_vertices_on_5nm_grid=True,pdk_density_checks_passed=175,
        pdk_density_checks_failed=0,exact_density_region_bbox_um=[0,0,1000,850],
        antenna_qualified=False,density_qualified=False,em_ir_qualified=False,
        physical_noise_qualified=False,physical_timing_qualified=False,
        physical_signoff_qualified=False,release_qualified=False,adopted=False,scope=__doc__))
    print('Exact filled GDS: fullMagicDRC0, completeuniqueLVS,55matchingpins and175/175PDKdensitychecks; othergates remainopen.')


if __name__=='__main__':
    main()
