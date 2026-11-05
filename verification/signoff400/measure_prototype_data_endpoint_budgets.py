"""Measure min/max data paths to every FF D pin, retaining mode exceptions."""
import argparse
import json
import os
from pathlib import Path
import re
import time

from common_v3 import save, sha, verify
from compiled_charge import execute
from resources import lease
from inventory_prototype_timing_endpoints import paths
from screen_prototype_decision_hold_phase_v3 import OPENROAD


def run(baseline, inventory, output):
    receipts = [p/'assessment.json' for p in (baseline, inventory)]
    records = [json.loads(p.read_text()) for p in receipts]
    for record in records:
        verify(record['artifacts'])
    lineage = {n: h for n, h in records[1]['input_sha256'].items()
               if n.endswith('/assessment.json') and 'equivalence' in n}
    if len(lineage) != 1 or any(records[0]['input_sha256'].get(n) != h for n, h in lineage.items()):
        # Conditional phase receipts pin their baseline, which pins equivalence.
        parent = next((Path(n) for n in records[0]['input_sha256']
                       if n.endswith('/assessment.json') and 'timing_' in n), None)
        if parent is None or sha(parent) != records[0]['input_sha256'][str(parent)]:
            raise ValueError('missing route lineage')
        inherited = json.loads(parent.read_text())['input_sha256']
        if len(lineage) != 1 or any(inherited.get(n) != h for n, h in lineage.items()):
            raise ValueError('different routed equivalence lineage')
    design = inventory/'routed.json'
    module = json.loads(design.read_text())['modules']['IntegerPLL_ProgrammedCore']
    targets = sorted(n.lstrip('\\') for n, c in module['cells'].items()
                     if c['type'].startswith(('sky130_fd_sc_hs__dfrtp_', 'sky130_fd_sc_hs__dfstp_')))
    if len(targets) != 481:
        raise ValueError('every implemented state cell required')
    original = baseline/'screen.tcl'
    if records[0]['input_sha256'].get(str(original)) != sha(original):
        raise ValueError('baseline Tcl changed')
    text = original.read_text().split('report_parasitic_annotation', 1)[0]
    queries = 'set capture [get_pins {'+' '.join(n+'/D' for n in targets)+'}]\n'
    queries += 'if {[llength $capture] != 481} {error "state D pin coverage differs"}\n'
    queries += 'report_checks -to $capture -path_delay min_max -group_path_count 100000 -endpoint_path_count 1 -sort_by_slack -digits 6\nexit\n'
    output.mkdir(parents=True, exist_ok=False)
    script = output/'data.tcl'
    script.write_text(text+queries)
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    os.environ.update(OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1')
    with lease(1, 4, deadline):
        execute([OPENROAD, '-exit', script], output/'data.log', deadline, 4)
    log = (output/'data.log').read_text()
    if re.search(r'\[ERROR|Error:|STA-(1648|1650)', log):
        raise ValueError('native data budget query error')
    checked = paths(log)
    if not checked or any(p['endpoint'] not in targets for p in checked):
        raise ValueError('missing or unexpected endpoint')
    detail = output/'paths.json'
    save(detail, checked)
    inputs = [*receipts, original, design, script, Path(__file__).resolve(), Path(OPENROAD)]
    save(output/'assessment.json', dict(input_sha256={str(p): sha(p) for p in inputs},
         artifacts={str(p): sha(p) for p in (detail, output/'data.log')},
         queried_state_D_pins=len(targets), reported_paths=len(checked),
         endpoint_checks={kind: len({p['endpoint'] for p in checked if p['kind']==kind}) for kind in ('min', 'max')},
         retained_capacity_mode_exceptions=True, all_modes_qualified=False, release_ready=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline', 'inventory', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    run(args.baseline.resolve(), args.inventory.resolve(), args.output.resolve())
