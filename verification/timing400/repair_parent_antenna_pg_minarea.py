#!/usr/bin/env python3
"""Add full-rule metal3 area to the isolated PG via-stack landings.

Magic found minimum-area errors invisible to the router's LEF checks. Add
0.6um-square M3 pads outside macro bodies, then require fresh parent routing
and complete GDS checks. Keep original check deadline and failed evidence.
"""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import subprocess
import time
from check_compact_clock_tree import verify
from check_compact_mapping import OPENROAD
from run_dco_qualification import ROOT,sha,save


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();base=ROOT/'build/timing400/release_001';source=base/'parent_dco_antenna_route_dedup_001'
    verify(source/'assessment.json');owner=json.loads((source/'owner.json').read_text());deadline=owner['deadline_uptime']
    failing=base/'parent_dco_antenna_layout_001/drc_errors.rpt';assert 'Metal3 minimum area' in failing.read_text()
    rows=[]
    for line in (source/'result.tsv').read_text().splitlines():
        f=line.split()
        if f[0]=='VIA' and f[3]=='M3M4_PR':
            a,b,c,d=map(int,f[4:]);x=(a+c)//2;y=(b+d)//2;rows.append((f[2],x,y))
    assert len(rows)==len(set(rows))==110
    bodies=[(147000,147000,607615,607615),(747000,147000,878000,278000),(747000,397000,873000,523000)]
    for net,x,y in rows:
        assert all(not(x-300<b[2] and x+300>b[0] and y-300<b[3] and y+300>b[1]) for b in bodies)
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    files=[Path(__file__).resolve(),Path(OPENROAD),source/'assessment.json',source/'route.odb',source/'owner.json',source/'result.tsv',failing]
    pins={str(p):sha(p) for p in files}
    save(out/'owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),deadline_uptime=deadline,
        original_owner=str(source/'owner.json'),total_budget_restarted=False,automatic_identical_retry=False))
    script=out/'repair.tcl';lines=[f'read_db {source}/route.odb','set block [ord::get_db_block]',
        'foreach net {VPWR VGND} {set sw($net) [odb::dbSWire_create [$block findNet $net] ROUTED]}',
        'set layer [[ord::get_db_tech] findLayer met3]']
    for net,x,y in rows:lines.append(f'odb::dbSBox_create $sw({net}) $layer {x-300} {y-300} {x+300} {y+300} STRIPE')
    lines += [f'write_db {out}/powered.odb',f'write_def {out}/powered.def',
        f'check_power_grid -net VPWR -error_file {out}/vpwr_errors.rpt',f'check_power_grid -net VGND -error_file {out}/vgnd_errors.rpt']
    script.write_text('\n'.join(lines)+'\n');pins[str(script)]=sha(script)
    with (out/'repair.log').open('x') as log:
        subprocess.run([OPENROAD,'-no_init','-exit',str(script)],stdout=log,stderr=subprocess.STDOUT,check=True,
            timeout=deadline-time.clock_gettime(time.CLOCK_BOOTTIME))
    log=(out/'repair.log').read_text();assert all(f'All shapes on net {n} are connected.' in log for n in ['VPWR','VGND'])
    for p,digest in pins.items():assert sha(p)==digest,p
    save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()},
        physical_db=str(out/'powered.odb'),owner=str(out/'owner.json'),openroad_power_connectivity_passed=True,
        m3_pg_pads_added=110,m3_pad_area_um2=.36,macro_interiors_unchanged=True,parent_signal_routes_require_rebuild=True,
        full_gds_drc_passed=False,antenna_qualified=False,release_qualified=False,adopted=False,scope=__doc__))
    print('Added110 outside-macro M3 PG pads of0.36um2; both grids connected. Fresh routing and full GDS checks required.')

if __name__=='__main__':main()
