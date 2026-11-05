#!/usr/bin/env python3
"""Bind final filled parent geometry checks to the exact manufactured geometry.

This receipt covers geometry, connectivity, PDK density and the checked antenna
methods. It does not qualify electrical parasitics, timing, supply/noise,
analog behavior or final release integration assumptions.
"""
import argparse
import json
from pathlib import Path
import re
import sys
import pya
from check_compact_clock_tree import verify
from run_dco_qualification import sha,save


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['stream','layout-audit','geometry','density-audit','native-antenna','output']:
        parser.add_argument('--'+name,required=True,type=Path)
    args=parser.parse_args();stream=args.stream.resolve();audit=args.layout_audit.resolve();geo=args.geometry.resolve()
    density=args.density_audit.resolve();native=args.native_antenna.resolve();out=args.output.resolve()
    s=verify(stream/'assessment.json');a=verify(audit/'assessment.json')
    g=verify(geo/'native_completion.json');b=verify(geo/'antenna/assessment.json');t=verify(geo/'topology/assessment.json')
    d=verify(density/'assessment.json');n=verify(native/'native_completion.json')
    assert a['filled'] and a['assembled_magic_drc_passed'] and a['assembled_lvs_passed'] and a['top_pins']==55
    assert s['parent_diode_instances']==564 and s['parent_well_tap_instances']==141
    assert s['all_source_macro_geometry_and_labels_preserved'] and s['all_original_parent_geometry_and_labels_preserved']
    assert s['all_added_fill_vertices_on_5nm_grid']
    gds=stream/'assembly.gds';digest=sha(gds)
    assert str(gds)==a['assembled_gds'] and digest==a['assembled_gds_sha256']==s['artifacts'][str(gds)]
    assert g['state']=='native_terminal' and set(g['exit_codes'].values())=={0}
    assert digest==g['input_sha256'][str(gds)]==b['input_sha256'][str(gds)]==t['input_sha256'][str(gds)]==n['input_sha256'][str(gds)]
    assert b['violations']==0 and b['all_drawing_mos_gate_area_enumerated_at_each_stage']
    assert len(b['formation_coverage'])==13 and all(r['violations']==0 for r in b['formation_coverage'])
    assert t['complete_port_connectivity_screen_passed'] and t['rectangular_macro_port_probes']==743
    assert d['constrained_density_checks']==175 and d['failed_density_checks']==0 and d['stock_density_checks_passed']
    den_native=Path(next(p for p in d['input_sha256'] if p.endswith('/native_completion.json')))
    dn=verify(den_native);assert dn['exit_code']==0 and dn['input_sha256'][str(gds)]==digest
    assert n['exit_code']==0
    log=(native/'antenna.log').read_text();feedback=re.findall(r'^ASSEMBLED_ANTENNA_FEEDBACK=(\d+)$',log,re.M)
    assert feedback==['0'] and log.count('ASSEMBLED_ANTENNA_BEGIN')==log.count('ASSEMBLED_ANTENNA_END')==1
    assert 'ASSEMBLED_ANTENNA_EXTRACTION_COMPLETE' in log and 'antennacheck finished.' in log
    assert 'Antenna violation detected' not in log and 'Effective antenna ratio' not in log
    assert max(map(int,re.findall(r'(\d+) gates analyzed\.',log)))>=16000
    assert log.rstrip().endswith('ASSEMBLED_ANTENNA_END')
    layout=pya.Layout();layout.read(str(gds));assert layout.dbu==.001
    top=layout.cell('IntegerPLL_400MHz_CandidateTop');box=top.bbox();bbox=[box.left,box.bottom,box.right,box.top]
    assert bbox==[0,0,1000000,850000],bbox
    owner_paths=[native/'owner.json',geo/'owner.json',den_native.parent/'owner.json']
    owners=[json.loads(p.read_text()) for p in owner_paths];assert len({o['deadline_uptime'] for o in owners})==1
    warnings=[line for line in log.splitlines() if 'warn' in line.lower() or 'freeMagic' in line]
    paths=[Path(__file__).resolve(),Path(sys.executable),gds,stream/'assessment.json',audit/'assessment.json',
        geo/'native_completion.json',geo/'antenna/assessment.json',geo/'topology/assessment.json',density/'assessment.json',
        den_native,native/'native_completion.json',native/'antenna.log',native/'antenna_feedback.txt',*owner_paths]
    out.mkdir(parents=True,exist_ok=False)
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in paths},artifacts={},assembled_gds=str(gds),assembled_gds_sha256=digest,
        assembled_magic_drc_rectangles=0,assembled_lvs_passed=True,all_three_macros_expanded=True,top_pins=55,
        exact_gds_bbox_nm=bbox,parent_diode_instances=564,parent_well_tap_instances=141,
        constrained_pdk_density_checks=175,pdk_density_failures=0,native_mos_only_antenna_feedback=0,
        independent_conservative_antenna_violations=0,forming_stages_checked=13,all_mos_gate_area_enumerated=True,
        independent_macro_port_probes=743,independent_port_connectivity_screen_passed=True,
        native_warning_lines=warnings,geometry_checks_passed=True,shared_original_layout_deadline=True,
        fill_aware_parasitics_qualified=False,antenna_method_and_integration_qualification_not_inferred=True,
        timing_qualified=False,physical_signoff_qualified=False,release_qualified=False,adopted=False,scope=__doc__))
    print('Exact filled GDS: full DRC0, unique LVS,175 density checks,13 conservative antenna stages and native antenna0; electrical/release gates open.')

if __name__=='__main__':main()
