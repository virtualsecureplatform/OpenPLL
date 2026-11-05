#!/usr/bin/env python3
"""Place a separate parent-level protection candidate beside failing DCO ports.

A local well tap and four HS diodes per reported DCO thermometer net provide an initial sizing
candidate. This is not proof of antenna ratios after routing. Existing macro
geometry, oscillator extraction and live simulations are untouched. Physical
supply routing, signal routing, forming-area and analog checks remain required.
"""
import argparse
from datetime import datetime,timezone
import json
import math
import os
from pathlib import Path
import re
import subprocess
import time
from check_compact_clock_tree import verify
from check_compact_mapping import OPENROAD,LEF
from run_dco_qualification import ROOT,sha,save


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();started=time.monotonic()
    base=ROOT/'build/timing400/release_001';source=base/'candidate_macro_power_repair_007'
    verify(source/'assessment.json');verify(base/'candidate_antenna_localization_003/assessment.json')
    records=base/'candidate_antenna_localization_003/debug_records.json'
    nets=sorted({alias.split('/',1)[1] for r in json.loads(records.read_text())
        for alias in r['named_port_aliases'] if 'C1FINE160_0/DCO_THERM[' in alias})
    assert len(nets)==131
    dco='IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160'
    lef=ROOT/f'openlane/{dco}/runs/c1fine_range_001/final/lef/{dco}.lef'
    text=lef.read_text();footprints=[(147000,147000,607615,607615),(747000,147000,878000,278000),(747000,397000,873000,523000)]
    occupied=[];plan=[];width=4320;height=3330
    for net in nets:
        body=re.search(r'^\s*PIN '+re.escape(net)+r'\s*$(.*?)^\s*END '+re.escape(net)+r'\s*$',text,re.M|re.S)[1]
        coords=list(map(float,re.search(r'RECT ([\d.]+) ([\d.]+) ([\d.]+) ([\d.]+)',body).groups()))
        cx=750000+round((coords[0]+coords[2])*500);cy=150000+round((coords[1]+coords[3])*500)
        options=[]
        for row in range(max(0,(cy-60000-13320)//3330),min(250,(cy+60000-13320)//3330)+1):
            if row%2:continue  # Separate islands vertically to avoid narrow nwell gaps.
            y=13320+row*3330
            for column in range(max(0,(cx-60000-10080)//480),min(2033,(cx+60000-10080)//480)+1):
                x=10080+column*480;box=(x,y,x+width,y+height)
                if any(box[0]<b[2] and box[2]>b[0] and box[1]<b[3] and box[3]>b[1] for b in footprints+occupied):continue
                options.append((abs(x+width//2-cx)+abs(y+height//2-cy),x,y,row,box))
        assert options,net
        distance,x,y,row,box=min(options)
        occupied.append((x-1920,y,x+width+1920,y+height))
        plan.append(dict(net=net,x_nm=x,y_nm=y,orient='R0' if row%2==0 else 'MX',diodes=4,
                         port_center_nm=[cx,cy],center_distance_nm=distance))
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    paths=[Path(__file__).resolve(),Path(OPENROAD),LEF,lef,source/'route.odb',source/'assessment.json',records,base/'candidate_antenna_localization_003/assessment.json']
    pins={str(p):sha(p) for p in paths}
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200-(time.monotonic()-started)
    save(out/'owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),deadline_uptime=deadline,total_budget_s=43200,automatic_identical_retry=False))
    save(out/'placement_plan.json',plan)
    script=out/'place.tcl'
    lines=[f'read_db {source}/route.odb','set block [ord::get_db_block]',
           'set master [[ord::get_db] findMaster sky130_fd_sc_hs__diode_2]',
           'if {[$master getWidth]!=960 || [$master getHeight]!=3330} {error "unexpected diode footprint"}']
    for index,row in enumerate(plan):
        lines.extend([f'set tap [odb::dbInst_create $block [[ord::get_db] findMaster sky130_fd_sc_hs__tapvpwrvgnd_1] parent_dco_antenna_tap_{index:03d}]',
            f'$tap setOrient {row["orient"]}',f'$tap setLocation {row["x_nm"]} {row["y_nm"]}',
            '$tap setPlacementStatus PLACED',
            '[$tap findITerm VPWR] connect [$block findNet VPWR]',
            '[$tap findITerm VGND] connect [$block findNet VGND]'])
        for number in range(4):
            name=f'parent_dco_antenna_{index:03d}_{number}'
            lines.extend([f'set inst [odb::dbInst_create $block $master {name}]',
                f'$inst setOrient {row["orient"]}',f'$inst setLocation {row["x_nm"]+480+number*960} {row["y_nm"]}',
                '$inst setPlacementStatus PLACED',f'[$inst findITerm DIODE] connect [$block findNet {{{row["net"]}}}]',
                'foreach pin {VPWR VPB} {[$inst findITerm $pin] connect [$block findNet VPWR]}',
                'foreach pin {VGND VNB} {[$inst findITerm $pin] connect [$block findNet VGND]}'])
    lines+=['check_placement -verbose',f'write_db {out}/placed.odb',f'write_def {out}/placed.def',f'write_verilog -include_pwr_gnd {out}/powered.v']
    script.write_text('\n'.join(lines)+'\n');pins[str(script)]=sha(script)
    save(out/'input_manifest.json',dict(input_sha256=pins,scope=__doc__))
    with (out/'place.log').open('x') as log:
        result=subprocess.run([OPENROAD,'-no_init','-exit',str(script)],stdout=log,stderr=subprocess.STDOUT,
                              timeout=max(1,deadline-time.clock_gettime(time.CLOCK_BOOTTIME)))
    assert result.returncode==0
    for p,digest in pins.items():assert sha(p)==digest,p
    save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()},
        protected_net_candidates=131,added_diode_instances=524,added_well_tap_instances=131,existing_macros_unchanged=True,
        placement_check_passed=True,physical_supply_connections_completed=False,signal_routing_completed=False,
        worst_port_center_distance_um=max(r['center_distance_nm'] for r in plan)*.001,
        antenna_qualified=False,analog_qualified=False,release_qualified=False,adopted=False,scope=__doc__))
    print('Placed 524 diode candidates and 131 local well taps on 131 DCO control nets; routing and all qualification remain pending.')

if __name__=='__main__':main()
