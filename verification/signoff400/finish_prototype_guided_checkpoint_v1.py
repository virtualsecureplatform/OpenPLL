"""Replay measured local guide corridors without moving cells or rerunning GRT.

Detailed routing and extraction are diagnostics; independent signoff is required.
The source checkpoint's absolute deadline is retained.
"""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import shutil
import sys
import time
from common_v3 import ROOT, save, sha, verify
from resources import lease
from compiled_charge_v2 import execute
from select_prototype_local_ECO_routes import route_records
sys.path.insert(0, str(ROOT/'verification/timing400'))
from check_compact_mapping import LIB, LEF, TECH, OPENROAD
from route_compact_candidate import RC_MODEL


def run(source, guides, phase, output):
    receipt = source/'assessment.json'
    r = json.loads(receipt.read_text())
    g = json.loads((guides/'assessment.json').read_text())
    for record in (r, g):
        verify(record['input_sha256']); verify(record['artifacts'])
    db = source/'antenna_repaired.odb'
    original_guides = source/'global.guide'
    sdc = phase/'enabled_phase.sdc'
    if any(g['input_sha256'].get(str(p)) != sha(p) for p in (receipt, db, original_guides)):
        raise ValueError('guide receipt must bind the same native checkpoint and original guides')
    if r['input_sha256'].get(str(sdc)) != sha(sdc):
        raise ValueError('same phase constraints required')
    if not g.get('nonlocal_guide_geometry_preserved') or not g.get('local_corridors'):
        raise ValueError('validated local-only guide replacement required')
    owner = source/'owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    if time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:
        raise TimeoutError('original checkpoint deadline expired')
    inputs = {str(p): sha(p) for p in (
        receipt, guides/'assessment.json', guides/'routing.guide', db, original_guides,
        owner, sdc, source/'route.tcl', Path(__file__).resolve(), Path(OPENROAD),
        LIB, LEF, TECH, RC_MODEL,
        Path(__file__).with_name('common_v3.py'), Path(__file__).with_name('resources.py'),
        Path(__file__).with_name('compiled_charge_v2.py'),
        Path(__file__).with_name('select_prototype_local_ECO_routes.py'))}
    output.mkdir(parents=True, exist_ok=False)
    save(output/'owner.json', dict(pid=os.getpid(), deadline_uptime=deadline,
        original_deadline_preserved=True, checkpoint=str(db), cpu_slots=4,
        memory_GiB=8, automatic_identical_retry=False))
    def status(state, **kw):
        save(output/'status.json', dict(state=state, release_ready=False, **kw))
    shutil.copyfile(guides/'routing.guide', output/'global.guide')
    inputs[str(output/'global.guide')] = sha(output/'global.guide')
    # Keep the proven output/extraction sequence, with only destination paths changed.
    frozen_tail = (source/'route.tcl').read_text().split('\ndetailed_route ', 1)
    if len(frozen_tail) != 2:
        raise ValueError('source detailed-route sequence missing')
    tail = 'detailed_route ' + frozen_tail[1].replace(str(source), str(output))
    script = output/'route.tcl'
    script.write_text(f'''read_lef {{{TECH}}}
read_lef {{{LEF}}}
read_liberty {{{LIB}}}
read_db {{{db}}}
source {{{sdc}}}
set_thread_count 4
set_propagated_clock [all_clocks]
set block [ord::get_db_block]
set_routing_layers -signal met1-met4 -clock met2-met4
set_wire_rc -signal -layer met2
set_wire_rc -clock -layer met3
read_guides {{{output/'global.guide'}}}
add_global_connection -net VDD -inst_pattern {{.*}} -pin_pattern {{^(VPWR|VPB)$}} -power
add_global_connection -net VSS -inst_pattern {{.*}} -pin_pattern {{^(VGND|VNB)$}} -ground
global_connect
check_placement -verbose
write_db {{{output/'antenna_repaired.odb'}}}
''' + tail)
    inputs[str(script)] = sha(script)
    save(output/'input_manifest.json', dict(input_sha256=inputs))
    os.environ.update(OMP_NUM_THREADS='4', GOMAXPROCS='4', OPENBLAS_NUM_THREADS='1')
    try:
        status('native_detailed_route_with_direct_local_guides_running')
        with lease(4, 8, deadline):
            execute([OPENROAD, '-no_init', '-exit', script], output/'route.log', deadline, 8)
        text = (output/'route.log').read_text()
        counts = re.findall(r'Number of violations = (\d+)', text)
        if ('CHECKPOINT_SIGNAL_ROUTE_COMPLETE' not in text or not counts
                or counts[-1] != '0' or (output/'route.drc').stat().st_size):
            raise ValueError('completed zero-DRC native detailed route required')
        if not all(f'All shapes on net {n} are connected.' in text for n in ('VDD', 'VSS')):
            raise ValueError('PG connectivity failed')
        inventory = Counter((output/'masters.txt').read_text().splitlines())
        if dict(inventory) != r['cell_inventory']:
            raise ValueError('guide-only reroute changed cell inventory')
        old = route_records((source/'route.def').read_text())
        new = route_records((output/'route.def').read_text())
        verify(inputs)
        save(output/'assessment.json', dict(input_sha256=inputs,
            artifacts={str(p): sha(p) for p in output.iterdir()
                       if p.is_file() and p.name not in ('status.json', 'assessment.json')},
            candidate_source_sha256=r['candidate_source_sha256'], cell_inventory=dict(inventory),
            digital_routing_completed=True, nominal_rc_extracted=True, router_drc_violations=0,
            database_power_grid_connected=True, related_fast_and_divided_clock_paths_preserved=True,
            local_guide_corridors=g['local_corridors'], nonlocal_guide_geometry_preserved=True,
            global_router_rerun=False, logical_ECO_reapplied=False,
            cell_inventory_unchanged=True, original_deadline_preserved=True,
            original_DEF_routing_records=len(old), final_DEF_routing_records=len(new),
            unchanged_DEF_routing_records=sum(new.get(n) == v for n, v in old.items()),
            independent_antenna_recheck_required=True,
            supplied_library_used_for_physical_routing_only=True,
            auxiliary_diode_load_is_conditional=True, digital_timing_qualified=False,
            physical_timing_qualified=False, release_ready=False))
        status('route_complete_independent_checks_pending')
    except BaseException as error:
        status('stopped_without_qualification', reason=repr(error))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'guides', 'phase', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    run(*(getattr(args, n).resolve() for n in ('source', 'guides', 'phase', 'output')))
