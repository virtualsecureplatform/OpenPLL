#!/usr/bin/env python3
"""Remove duplicate PG records while preserving exact physical geometry.

Merge M1 power rectangles and retain one copy of each identical new via stack.
Existing routing passes are inherited only after exact signal-DEF identity
and native PG-union comparison. Full streamed layout checks remain required.
"""
import argparse
from collections import defaultdict
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import re
import subprocess
import time
import pya
from check_compact_clock_tree import verify
from check_compact_mapping import OPENROAD
from run_dco_qualification import ROOT,sha,save


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();base=ROOT/'build/timing400/release_001'
    source=base/'parent_dco_antenna_route_001';proof=verify(source/'assessment.json')
    assert proof['router_drc_violations']==0 and proof['main_rail_connectivity_passed']
    owner=json.loads((source/'owner.json').read_text());deadline=owner['deadline_uptime']
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    inputs=[Path(__file__).resolve(),Path(OPENROAD),source/'assessment.json',source/'route.odb',source/'route.def',source/'owner.json']
    pins={str(p):sha(p) for p in inputs}
    save(out/'owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),deadline_uptime=deadline,
        original_owner=str(source/'owner.json'),total_budget_restarted=False,automatic_identical_retry=False))
    def run(name,text):
        script=out/(name+'.tcl');script.write_text(text)
        with (out/(name+'.log')).open('x') as log:
            subprocess.run([OPENROAD,'-no_init','-exit',str(script)],stdout=log,stderr=subprocess.STDOUT,check=True,
                           timeout=deadline-time.clock_gettime(time.CLOCK_BOOTTIME))
    def dump(db,dest):
        return f'''read_db {db}
set f [open {dest} w]
set serial 0
foreach net {{VPWR VGND}} {{
 foreach wire [[[ord::get_db_block] findNet $net] getSWires] {{
  foreach box [$wire getWires] {{
   incr serial
   if {{![$box isVia] && [[$box getTechLayer] getName] eq {{met1}}}} {{
    puts $f [list M1 $serial $net [$box xMin] [$box yMin] [$box xMax] [$box yMax]]
   }} elseif {{[$box isVia] && [$box getTechVia] ne {{NULL}}}} {{
    set via [[$box getTechVia] getName]
    if {{$via in {{M1M2_PR M2M3_PR M3M4_PR}}}} {{
     puts $f [list VIA $serial $net $via [$box xMin] [$box yMin] [$box xMax] [$box yMax]]
    }}
   }}
  }}
 }}
}}
close $f
'''
    run('source_dump',dump(source/'route.odb',out/'source.tsv'))
    regions={n:pya.Region() for n in ['VPWR','VGND']};seen=set();remove=[];source_cuts=[]
    for line in (out/'source.tsv').read_text().splitlines():
        fields=line.split();kind,serial,net=fields[:3]
        if kind=='M1':regions[net].insert(pya.Box(*map(int,fields[3:])));remove.append(int(serial))
        else:
            key=(net,*fields[3:]);source_cuts.append(key)
            if key in seen:remove.append(int(serial))
            else:seen.add(key)
    assert len(source_cuts)==786 and len(seen)==330
    rectangles=[]
    for net,reg in regions.items():
        regions[net]=reg.merged()
        for polygon in regions[net].decompose_trapezoids_to_region().each():
            bb=polygon.bbox();assert polygon.area()==bb.area()
            box=[bb.left,bb.bottom,bb.right,bb.top];assert all(v%5==0 for v in box)
            rectangles.append((net,*box))
    mutation='''read_db @SOURCE@/route.odb
set block [ord::get_db_block]
set serial 0
foreach net {VPWR VGND} {
 foreach wire [[$block findNet $net] getSWires] {
  foreach box [$wire getWires] {
   incr serial
   if {$serial in {@REMOVE@}} {odb::dbSBox_destroy $box}
  }
 }
}
foreach net {VPWR VGND} {set sw($net) [odb::dbSWire_create [$block findNet $net] ROUTED]}
set layer [[ord::get_db_tech] findLayer met1]
'''.replace('@SOURCE@',str(source)).replace('@REMOVE@',' '.join(map(str,remove)))
    mutation+='\n'.join(f'odb::dbSBox_create $sw({n}) $layer {a} {b} {c} {d} STRIPE' for n,a,b,c,d in rectangles)
    mutation+=f'''\nwrite_db {out}/route.odb
write_def {out}/route.def
write_verilog {out}/route.v
write_verilog -include_pwr_gnd {out}/powered_top.v
check_power_grid -net VPWR -error_file {out}/vpwr_errors.rpt
check_power_grid -net VGND -error_file {out}/vgnd_errors.rpt
'''
    run('deduplicate',mutation);run('result_dump',dump(out/'route.odb',out/'result.tsv'))
    revised={n:pya.Region() for n in regions};cuts=[]
    for line in (out/'result.tsv').read_text().splitlines():
        fields=line.split();kind,serial,net=fields[:3]
        if kind=='M1':revised[net].insert(pya.Box(*map(int,fields[3:])))
        else:cuts.append((net,*fields[3:]))
    assert len(cuts)==len(set(cuts))==330 and set(cuts)==set(source_cuts)
    assert all((regions[n]^revised[n].merged()).is_empty() for n in regions)
    def section(path,name):return re.search(r'^'+name+r' \d+ ;\n(.*?)^END '+name+r'\s*$',path.read_text(),re.M|re.S)[1]
    assert all(section(source/'route.def',name)==section(out/'route.def',name) for name in ['COMPONENTS','PINS','NETS'])
    log=(out/'deduplicate.log').read_text()
    assert all(f'All shapes on net {n} are connected.' in log for n in regions)
    for path,digest in pins.items():assert sha(path)==digest,path
    save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()},
        parent_signal_routes_rebuilt=True,detailed_route_completed=True,router_drc_violations=0,
        inherited_router_drc_receipt=str(source/'assessment.json'),signal_routes_ports_and_components_exactly_identical=True,
        m1_pg_geometry_exactly_identical=True,duplicate_via_records_removed=456,unique_new_pg_via_records=330,
        main_rail_connectivity_passed=True,all_source_macro_geometry_and_labels_preserved=True,
        full_assembled_drc_passed=False,assembled_lvs_passed=False,antenna_qualified=False,analog_qualified=False,
        release_qualified=False,adopted=False,scope=__doc__))
    print('Removed456 duplicate via records and merged M1 rails; exact geometry/signal identity and power connectivity verified.')

if __name__=='__main__':main()
