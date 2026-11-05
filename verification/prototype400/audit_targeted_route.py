#!/usr/bin/env python3
"""Audit retained targeted routing, allowing only explicit PG SPECIAL pin tags.

The original router run completed successfully; its bytewise pin comparison
rejected DEF's added SPECIAL tags. No routing is repeated or changed here.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys
from common import ROOT,save,sha,verify
sys.path.insert(0,str(ROOT/'verification/timing400'))
from check_bbpd_repair_identity import design,section


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('source','route','output'):p.add_argument('--'+n,required=True,type=Path)
    a=p.parse_args();source=a.source.resolve();route=a.route.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    r=json.loads((source/'assessment.json').read_text());verify(r['input_sha256']);verify(r['artifacts'])
    log=(route/'route.log').read_text();counts=re.findall(r'Number of violations = (\d+)',log)
    assert counts and counts[-1]=='0' and (route/'route.drc').stat().st_size==0
    assert 'Complete detail routing.' in log and '[ERROR' not in log
    assert all(f'All shapes on net {n} are connected.' in log for n in ('VPWR','VGND'))
    oldcells,oldpins,oldnets=design(source/'route.def');placedcells,placedpins,_=design(route/'placed.def')
    cells,pins,nets=design(route/'route.def')
    assert cells==placedcells and all(cells[n]==v for n,v in oldcells.items())
    assert all(pins[k]==v for k,v in oldpins.items()) and pins==placedpins
    oldp=section(source/'route.def','PINS');newp=section(route/'route.def','PINS')
    # Require the exact original text after removing only new tags from the two rails.
    def strip_special(text):
        return re.sub(r'(-\s+(?:VPWR|VGND)\s+\+ NET (?:VPWR|VGND)) \+ SPECIAL',r'\1',text)
    assert strip_special(newp)==oldp
    assert newp.count('+ SPECIAL')==2 and '+ SPECIAL' not in oldp
    def normalize(text):return re.sub(r'\bFIXED\b','ROUTED',' '.join(text.split()))
    assert normalize(section(source/'route.def','SPECIALNETS'))==normalize(section(route/'route.def','SPECIALNETS'))
    plan=json.loads((route/'extra_placement_plan.json').read_text());selected={r['net'] for r in plan};assert len(selected)==len(plan)==10
    frozen=[n for n,body in oldnets.items() if n not in selected and re.search(r'\bROUTED\b',body)]
    assert len(frozen)==359 and all(normalize(nets[n])==normalize(oldnets[n]) for n in frozen)
    for i,row in enumerate(plan):
        for number in range(4):assert pins[f'parent_extra_antenna_{i:02d}_{480+number*960}','DIODE']==row['net']
    # A wrongly connected added protection device must fail the binding check.
    corrupt=dict(pins);key=next(k for k in corrupt if k[0].startswith('parent_extra_antenna') and k[1]=='DIODE')
    corrupt[key]='REFCLK';assert corrupt!=placedpins
    files=[Path(__file__).resolve(),source/'assessment.json',source/'route.def',route/'route.log',route/'route.drc',route/'route.odb',route/'route.def',route/'placed.def',route/'extra_placement_plan.json',route/'powered.v']
    for name in ('route.odb','route.def','powered.v'):(out/name).symlink_to(route/name)
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in files},
         artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()},router_drc_violations=0,
         exact_macro_bindings_preserved=True,all_protection_cell_bindings_verified=True,negative_diode_binding_rejected=True,
         main_rail_database_connectivity_pass=True,all_original_power_geometry_preserved=True,
         unchanged_background_signal_routes=len(frozen),target_nets=sorted(selected),
         explicit_pg_special_tags_only_pin_change=True,physical_geometry_changed_by_this_audit=False,
         assembled_drc_pass=False,assembled_lvs_pass=False,antenna_qualified=False,release_qualified=False))
    save(out/'status.json',dict(state='targeted_route_audit_pass_pending_gds_checks',release_qualified=False))
    print('Targeted route audited: router DRC0, 359 unchanged background routes, exact macro/protection bindings.')


if __name__=='__main__':main()
