#!/usr/bin/env python3
"""Connect physical constant drivers before validating a compact placement."""
import argparse
from collections import Counter
import json
from pathlib import Path

from check_compact_mapping import ALLOWED, LIB, TECH, LEF, OPENROAD, run
from check_compact_clock_tree import verify
from run_dco_qualification import sha, save


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--placement',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();source=args.placement.resolve();out=args.output.resolve()
    receipt=verify(source/'assessment.json')
    assert receipt['restricted_master_inventory_passed']
    out.mkdir(parents=True,exist_ok=False)
    files=[Path(__file__).resolve(),Path(__file__).with_name('check_compact_clock_tree.py').resolve(),
           Path(__file__).with_name('check_compact_mapping.py').resolve(),Path(OPENROAD),LIB,TECH,LEF,
           source/'assessment.json',source/'placed.odb']
    pins={str(p):sha(p) for p in files}
    task=out/'ties.tcl'
    task.write_text(f'''read_lef {TECH}
read_lef {LEF}
read_liberty {LIB}
read_db {source}/placed.odb
set block [ord::get_db_block]
set master [[ord::get_db] findMaster sky130_fd_sc_hs__conb_1]
foreach {{name output}} {{one_ HI zero_ LO}} {{
 set net [$block findNet $name]
 if {{$net eq {{NULL}}}} {{error "missing expected constant net $name"}}
 set sinks [$net getITerms]
 if {{[llength $sinks] == 0}} {{error "constant net has no sinks"}}
 foreach sink $sinks {{
  if {{[$sink getIoType] ne {{INPUT}}}} {{error "constant net already has a driver"}}
 }}
 set tie [odb::dbInst_create $block $master constant_tie_$output]
 $tie setLocation {{*}}[[[lindex $sinks 0] getInst] getLocation]
 $tie setPlacementStatus PLACED
 $net setSigType SIGNAL
 [$tie findITerm $output] connect $net
}}
repair_tie_fanout sky130_fd_sc_hs__conb_1/HI
repair_tie_fanout sky130_fd_sc_hs__conb_1/LO
detailed_placement
check_placement -verbose
write_db {out}/placed.odb
write_verilog {out}/placed.v
set inventory [open {out}/masters.txt w]
foreach inst [$block getInsts] {{puts $inventory [[$inst getMaster] getName]}}
close $inventory
exit
''')
    assert run([OPENROAD,'-exit',task],out/'ties.log')==0
    assert 'Error:' not in (out/'ties.log').read_text()
    masters=Counter((out/'masters.txt').read_text().splitlines())
    assert set(masters)<=ALLOWED and masters['sky130_fd_sc_hs__conb_1']>=2
    for path,digest in pins.items():assert sha(Path(path))==digest,path
    save(out/'assessment.json',dict(input_sha256=pins,
        artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()},
        master_counts=dict(masters),cell_types=len(masters),cells=sum(masters.values()),
        restricted_master_inventory_passed=True,physical_constants_connected=True,
        adopted=False,physical_timing_qualified=False,release_qualified=False,
        scope='Physical constant connectivity only. Functional equivalence and all timing/signoff checks remain separate.'))


if __name__=='__main__':main()
