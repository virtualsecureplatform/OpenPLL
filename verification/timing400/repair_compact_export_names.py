#!/usr/bin/env python3
"""Repair internal-net/output-port name collisions without moving geometry.

After buffering an output port, its former net must not retain the port's
Verilog identifier. Otherwise write_verilog aliases distinct physical nets.
Independent LVS and logical checks are still required on the new export.
"""
import argparse
from collections import Counter
from pathlib import Path
import re

from check_compact_clock_tree import verify
from check_compact_mapping import LIB,TECH,LEF,OPENROAD,run
from route_compact_candidate import RC_MODEL
from run_dco_qualification import sha,save


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--route',required=True,type=Path)
    parser.add_argument('--cts',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();source=args.route.resolve();cts=args.cts.resolve();out=args.output.resolve()
    receipt=verify(source/'assessment.json')
    assert receipt['restricted_master_inventory_passed']
    assert receipt['input_sha256'][str(cts/'cts.tcl')]==sha(cts/'cts.tcl')
    out.mkdir(parents=True,exist_ok=False)
    files=[Path(__file__).resolve(),Path(OPENROAD),LIB,TECH,LEF,RC_MODEL,source/'assessment.json',
           source/'route.odb',source/'route.def',source/'route.v',cts/'cts.tcl']
    pins={str(p):sha(p) for p in files}
    task=out/'export.tcl'
    task.write_text(f'''read_lef {TECH}
read_lef {LEF}
read_liberty {LIB}
read_db {source}/route.odb
set_thread_count 4
set block [ord::get_db_block]
set count 0
foreach net [$block getNets] {{
 set port [$block findBTerm [$net getName]]
 if {{$port eq {{NULL}} || [$port getNet] eq $net}} {{continue}}
 if {{[$port getIoType] ne {{OUTPUT}}}} {{error "unexpected input-port collision"}}
 set old [$net getName]
 set new ${{old}}__internal_export
 if {{[$block findNet $new] ne {{NULL}}}} {{error "new internal net name already exists"}}
 if {{![$net rename $new]}} {{error "net rename failed"}}
 puts "EXPORT_NAME_REPAIR\t$old\t$new"
 incr count
}}
if {{$count != 3}} {{error "unexpected collision count: $count"}}
write_db {out}/route.odb
write_def {out}/route.def
write_verilog {out}/route.v
define_process_corner -ext_model_index 0 RCX_NOM
extract_parasitics -ext_model_file {RC_MODEL} -corner 0
write_spef {out}/route.nom.spef
set inventory [open {out}/masters.txt w]
foreach inst [$block getInsts] {{puts $inventory [[$inst getMaster] getName]}}
close $inventory
exit
''')
    code=run([OPENROAD,'-exit',task],out/'export.log')
    log=(out/'export.log').read_text()
    assert code==0 and 'Error:' not in log,log[-2500:]
    renames=dict(re.findall(r'^EXPORT_NAME_REPAIR\t([^\n\t]+)\t([^\n]+)',log,re.M))
    assert set(renames)=={'DLF_CODE[3]','DLF_CODE[5]','DLF_CODE[7]'}
    masters=Counter((out/'masters.txt').read_text().splitlines())
    assert dict(masters)==receipt['master_counts']
    # DEF should change only the three net identifiers. This catches any
    # accidental movement, rerouting, PG or connectivity mutation in this step.
    old_def=(source/'route.def').read_text();new_def=(out/'route.def').read_text()
    section=re.search(r'^NETS [0-9]+ ;\n(.*?)^END NETS',old_def,re.M|re.S)
    assert section
    body=section[1]
    for before,after in renames.items():
        # Replace only net declarations; matching port names must be retained.
        body,n=re.subn(r'(^\s*- )'+re.escape(before)+r'(?=\s)',
            lambda m:m[1]+after,body,flags=re.M)
        assert n==1,(before,n)
    old_def=old_def[:section.start(1)]+body+old_def[section.end(1):]
    assert old_def==new_def,'DEF differs beyond audited net identifier changes'
    for path,digest in pins.items():assert sha(Path(path))==digest,path
    save(out/'assessment.json',dict(input_sha256=pins,
        artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()},
        renamed_internal_nets=renames,def_geometry_and_connectivity_unchanged=True,
        master_counts=dict(masters),functional_cell_types=receipt['functional_cell_types'],
        restricted_master_inventory_passed=True,nominal_signal_rc_extracted=True,
        adopted=False,physical_timing_qualified=False,release_qualified=False,scope=__doc__))
    print('Repaired three export-name collisions; DEF otherwise identical',flush=True)


if __name__=='__main__':main()
