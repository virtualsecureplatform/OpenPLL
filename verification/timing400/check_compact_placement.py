#!/usr/bin/env python3
"""Isolated placement feasibility screen of a proved compact mapping.

Uses supplied TT timing, estimated placement parasitics, and diagnostic clock
exceptions. This does not qualify timing or replace the release candidate.
"""
import argparse
import json
from pathlib import Path
import re

from check_compact_mapping import ALLOWED, LIB, TECH, LEF, OPENROAD, run
from run_dco_qualification import ROOT, sha, save


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mapping', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    mapping = args.mapping.resolve()
    receipt = json.loads((mapping / 'assessment.json').read_text())
    assert receipt['all_transition_and_output_functions_equivalent']
    assert receipt['corrupted_data_function_rejected']
    for path, digest in {**receipt['sha256'], **receipt['artifacts']}.items():
        assert sha(Path(path)) == digest, path
    assert set(receipt['allowed_compact_types']) == ALLOWED
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    inputs = [Path(__file__).resolve(), Path(OPENROAD), LIB, TECH, LEF,
              mapping / 'assessment.json', mapping / 'compact/mapped.v',
              mapping / 'compact/capacity.tcl']
    pins = {str(p): sha(p) for p in inputs}
    # Retain the exact diagnostic clock assumptions. Insert the floorplan
    # before constraints so generated-clock pin collections resolve normally.
    original = (mapping / 'compact/capacity.tcl').read_text()
    assert original.count('link_design IntegerPLL_AcquiringCore\n') == 1
    script = original.split('report_checks -path_delay max')[0].replace(
        'link_design IntegerPLL_AcquiringCore\n',
        'link_design IntegerPLL_AcquiringCore\n'
        'initialize_floorplan -utilization 35 -aspect_ratio 1 -core_space 10 -site unit\n')
    all_cells = set(re.findall(r'\bcell\s*\(\s*"?([^"\s)]+)', LIB.read_text()))
    excluded = sorted(all_cells - ALLOWED)
    script += 'set_thread_count 4\nset_dont_use [get_lib_cells {' + ' '.join(excluded) + '}]\n'
    script += f'''set_wire_rc -signal -layer met2
set_wire_rc -clock -layer met3
set_placement_padding -global -left 1 -right 1
make_tracks
place_pins -hor_layers met3 -ver_layers met4
global_placement -timing_driven -density 0.55
estimate_parasitics -placement
repair_design
estimate_parasitics -placement
repair_timing -setup -setup_margin 0.10 -max_iterations 100
detailed_placement
estimate_parasitics -placement
check_placement -verbose
report_checks -path_delay max -group_path_count 1 -digits 6
report_checks -path_delay min -group_path_count 1 -digits 6
report_check_types -max_slew -max_capacitance -min_pulse_width
check_setup -verbose
write_db {out}/placed.odb
write_verilog {out}/placed.v
set inventory [open {out}/masters.txt w]
foreach inst [[ord::get_db_block] getInsts] {{puts $inventory [[$inst getMaster] getName]}}
close $inventory
exit
'''
    task = out / 'placement.tcl'
    task.write_text(script)
    code = run([OPENROAD, '-exit', task], out / 'placement.log')
    log = (out / 'placement.log').read_text()
    assert code == 0 and 'Error:' not in log, log[-2500:]
    from collections import Counter
    masters = Counter((out / 'masters.txt').read_text().splitlines())
    assert set(masters) <= ALLOWED, set(masters) - ALLOWED
    slacks = {}
    for block in log.split('Startpoint:')[1:]:
        group = re.search(r'Path Group: ([^\n]+)', block)
        kind = re.search(r'Path Type: (max|min)', block)
        slack = re.search(r'(-?\d+\.\d+)\s+slack', block)
        if group and kind and slack:
            slacks[f'{group[1]}:{kind[1]}'] = float(slack[1])
    assert 'PLLOUT:max' in slacks and 'PLLOUT:min' in slacks
    for path, digest in pins.items():
        assert sha(Path(path)) == digest, path
    save(out / 'assessment.json', dict(
        input_sha256=pins, artifacts={str(p): sha(p) for p in out.iterdir() if p.is_file()},
        master_counts=dict(masters), cell_types=len(masters), cells=sum(masters.values()),
        diagnostic_slack_ns=slacks, mapping_identity_verified=True,
        restricted_master_inventory_passed=True, adopted=False,
        physical_timing_qualified=False, release_qualified=False,
        scope=__doc__))
    print(json.dumps(dict(cell_types=len(masters), slacks=slacks)), flush=True)


if __name__ == '__main__':
    main()
