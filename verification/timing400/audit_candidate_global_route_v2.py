#!/usr/bin/env python3
"""Check guide coverage and unchanged macro connectivity; not detailed routing."""
import argparse
import json
from pathlib import Path
import re
import subprocess

from audit_candidate_floorplan import check
from check_compact_clock_tree import verify
from check_compact_mapping import OPENROAD
from run_dco_qualification import ROOT, sha, save


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--route', required=True, type=Path)
    parser.add_argument('--floorplan', required=True, type=Path)
    args = parser.parse_args()
    out, floorplan = args.route.resolve(), args.floorplan.resolve()
    assert not (out/'assessment.json').exists()
    verify(floorplan/'assessment.json')
    power_audit = ROOT/'build/timing400/release_001/candidate_power_grid_audit_001/assessment.json'
    power = verify(power_audit)
    assert power['main_rail_connectivity_passed']
    source_db = Path(re.search(r'^read_db (.+)$',(out/'route.tcl').read_text(),re.M)[1])
    assert sha(source_db) == power['input_sha256'][str(source_db)]
    log = (out/'route.log').read_text().split('Final congestion report:')[-1]
    total = re.search(r'^Total\s+(\d+)\s+(\d+)\s+([\d.]+)%\s+(\d+) /\s*(\d+) /\s*(\d+)', log, re.M)
    assert total
    overflow = int(total[6])
    count = int(re.search(r'Routed nets: (\d+)',log)[1])
    script = f'''read_db {out}/guided.odb
set block [ord::get_db_block]
set f [open {out}/database_audit.tsv w]
foreach inst [$block getInsts] {{
    foreach pin [$inst getITerms] {{
        puts $f [join [list PIN [$inst getName] [[$pin getMTerm] getName] [[$pin getNet] getName]] "\\t"]
    }}
}}
foreach net [$block getNets] {{
    puts $f [join [list NET [$net getName] [$net getSigType]] "\\t"]
}}
foreach term [$block getBTerms] {{
    set rectangles 0
    foreach pin [$term getBPins] {{incr rectangles [llength [$pin getBoxes]]}}
    puts $f [join [list PORT [$term getName] $rectangles] "\\t"]
}}
close $f
'''
    (out/'database_audit.tcl').write_text(script)
    with (out/'database_audit.log').open('w') as stream:
        subprocess.run([OPENROAD,'-no_init','-exit',str(out/'database_audit.tcl')],
                       stdout=stream,stderr=subprocess.STDOUT,check=True,timeout=60)
    connections, signals, ports = {}, set(), {}
    for line in (out/'database_audit.tsv').read_text().splitlines():
        f = line.split('\t')
        if f[0] == 'PIN':
            pins = connections.setdefault(f[1],{})
            assert f[2] not in pins
            pins[f[2]] = f[3]
        elif f[0] == 'NET':
            if f[2] not in ('POWER','GROUND'):
                signals.add(f[1])
        else:
            assert f[0] == 'PORT' and f[1] not in ports
            ports[f[1]] = int(f[2])
    check(connections)
    assert len(ports) == 55 and all(v>0 for v in ports.values())
    guides = re.findall(r'^(\S+)\n\(\n', (out/'route.guide').read_text(),re.M)
    assert len(guides) == len(set(guides)) == count == 357
    assert set(guides) == signals
    assert {'VPB','VNB'} <= signals
    assert all(f'All shapes on net {n} are connected.' in log for n in ('VPWR','VGND'))
    inputs = [Path(__file__).resolve(),Path(__file__).with_name('audit_candidate_floorplan.py'),
              Path(OPENROAD),floorplan/'assessment.json',floorplan/'floorplan.odb',
              power_audit,source_db]
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in inputs},
        artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()},
        signal_nets_with_guides=count,guide_net_coverage_complete=True,
        macro_connections_rechecked=674,top_scalar_pins_with_geometry=55,
        global_routing_overflow=overflow,global_route_capacity_screen_passed=overflow==0,
        signal_wirelength_um=int(re.search(r'Total wirelength: (\d+) um',log)[1]),
        main_rail_connectivity_passed=True,body_bias_nets_included_in_signal_route=True,
        power_grid_completed=False,detailed_route_completed=False,
        extracted_rc_qualified=False,physical_timing_qualified=False,
        assembled_lvs_passed=False,release_qualified=False,adopted=False,scope=__doc__))
    print(f'Checked357guide nets including body bias,674macro bindings and55pins; overflow={overflow}.')


if __name__ == '__main__':
    main()
