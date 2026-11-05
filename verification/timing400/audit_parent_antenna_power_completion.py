#!/usr/bin/env python3
"""Recover completed PG construction evidence after a log-text wrapper mismatch.

The native script completed both PG checks and output writes. Its Python
wrapper subsequently expected the wrong success wording. Verify all pinned
inputs and produced outputs without repeating the native mutation/check.
"""
import argparse
import json
from pathlib import Path
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT,sha,save


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();base=ROOT/'build/timing400/release_001'
    source=base/'parent_dco_antenna_power_002'
    manifest=json.loads((source/'input_manifest.json').read_text())
    for p,digest in manifest['input_sha256'].items():assert sha(p)==digest,p
    verify(base/'parent_dco_antenna_placement_002/assessment.json')
    log=(source/'connect.log').read_text()
    assert all(f'[INFO PSM-0040] All shapes on net {net} are connected.' in log for net in ['VPWR','VGND'])
    assert '[ERROR' not in log
    plan=json.loads((source/'power_plan.json').read_text());assert len(plan)==262
    assert {r['index'] for r in plan}==set(range(131))
    assert all({r['net'] for r in plan if r['index']==i}=={'VPWR','VGND'} for i in range(131))
    for name in ['powered.odb','powered.def','powered.v']:assert (source/name).stat().st_size>0
    tcl=(source/'connect.tcl').read_text()
    assert 'check_power_grid -net VPWR' in tcl and 'check_power_grid -net VGND' in tcl
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    paths=[Path(__file__).resolve(),source/'input_manifest.json',source/'owner.json',source/'connect.log',source/'connect.tcl',source/'power_plan.json']
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in paths},
        artifacts={str(source/name):sha(source/name) for name in ['powered.odb','powered.def','powered.v']},
        source=str(source),physical_db=str(source/'powered.odb'),owner=str(source/'owner.json'),
        native_pg_construction_and_checks_completed=True,openroad_power_connectivity_passed=True,
        connected_island_rail_pairs=131,via_stack_insertions=262,
        wrapper_exit=1,wrapper_failure_reason='Wrong expected success wording after completed native checks: actual PSM-0040 says All shapes on net ... are connected.',
        native_checks_repeated=False,parent_signal_routes_require_rebuild=True,
        full_gds_drc_passed=False,lvs_qualified=False,antenna_qualified=False,analog_qualified=False,release_qualified=False,adopted=False,scope=__doc__))
    print('Recovered completed PG checks for both supplies; native checks were not repeated. Full signal reroute remains required.')

if __name__=='__main__':main()
