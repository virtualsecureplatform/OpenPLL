#!/usr/bin/env python3
"""Audit the completed top route; full assembled signoff remains separate."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import time

from audit_candidate_power_grid import dump
from check_compact_clock_tree import verify
from check_compact_mapping import OPENROAD
from run_dco_qualification import ROOT, sha, save


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--route', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    route, out = args.route.resolve(), args.output.resolve()
    assert not out.exists()
    base = ROOT/'build/timing400/release_001'
    source = base/'candidate_power_grid_013'
    power = base/'candidate_power_grid_audit_001/assessment.json'
    global_report = base/'candidate_global_route_004/assessment.json'
    assert verify(power)['main_rail_connectivity_passed']
    assert verify(global_report)['global_route_capacity_screen_passed']
    owner = json.loads((route/'owner.json').read_text())
    assert not (Path('/proc')/str(owner['wrapper_pid'])).exists()
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < owner['deadline_uptime']
    manifest = json.loads((route/'input_manifest.json').read_text())
    for path, digest in manifest['input_sha256'].items():
        assert sha(path) == digest, path
    log = (route/'run.log').read_text()
    assert '[ERROR' not in log and 'Complete detail routing.' in log
    counts = re.findall(r'Number of violations = (\d+)',log)
    assert counts and int(counts[-1]) == 0 and (route/'route.drc').stat().st_size == 0
    assert all(f'All shapes on net {n} are connected.' in log for n in ('VPWR','VGND'))
    out.mkdir(parents=True)
    con0, boxes0 = dump(out,source/'power_grid.odb','source_power')
    con1, boxes1 = dump(out,route/'route.odb','routed_power')
    assert con0 == con1 and boxes0 == boxes1
    script = f'''read_db {route}/route.odb
set f [open {out}/signal_wires.tsv w]
foreach net [[ord::get_db_block] getNets] {{
    if {{[$net getSigType] ni {{POWER GROUND}}}} {{
        if {{[$net getWire] == "NULL"}} {{error "signal net has no detailed wire"}}
        puts $f [$net getName]
    }}
}}
close $f
'''
    (out/'signal_wires.tcl').write_text(script)
    with (out/'signal_wires.log').open('w') as stream:
        subprocess.run([OPENROAD,'-no_init','-exit',str(out/'signal_wires.tcl')],
                       stdout=stream,stderr=subprocess.STDOUT,check=True,timeout=60)
    nets = (out/'signal_wires.tsv').read_text().splitlines()
    assert len(nets) == len(set(nets)) == 357 and {'VPB','VNB'} <= set(nets)
    files = [Path(__file__).resolve(),Path(__file__).with_name('audit_candidate_power_grid.py'),
        Path(OPENROAD),source/'power_grid.odb',power,global_report,route/'input_manifest.json',
        route/'owner.json',route/'run.log',route/'route.odb',route/'route.def',
        route/'route.v',route/'route.drc',route/'route.coverage']
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in files},
        artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()},
        detailed_route_completed=True,router_drc_violations=0,signal_nets_with_detailed_wire=357,
        macro_connections_preserved=674,all_power_shapes_and_vias_unchanged=True,
        main_rail_connectivity_passed=True,completed_within_original_12h_deadline=True,
        full_assembled_drc_passed=False,assembled_lvs_passed=False,
        antenna_qualified=False,em_ir_qualified=False,extracted_rc_qualified=False,
        physical_timing_qualified=False,release_qualified=False,adopted=False,scope=__doc__))
    print('Audited357detailed wires,674macro bindings and unchanged power geometry; routerDRC0.')


if __name__ == '__main__':
    main()
