#!/usr/bin/env python3
"""Extract min/nom/max parent-wire RC from the current antenna-repaired route.

This is parent routing evidence only. Macro internals, generated GDS fill,
intrinsic pin capacitance and process enclosure are not qualified by OpenRCX.
Do not combine these capacitances with a full-GDS network or adopt them twice.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import time
from check_compact_clock_tree import verify
from check_compact_mapping import OPENROAD
from run_dco_qualification import ROOT, sha, save


def main():
    base = ROOT/'build/timing400/release_001'
    route = base/'parent_dco_antenna_targeted_011'
    out = base/'current_parent_wire_rc_001'
    r = verify(route/'assessment.json')
    final = base/'parent_dco_antenna_final_geometry_011/assessment.json'
    g = verify(final)
    assert r['router_drc_violations'] == 0 and g['geometry_checks_passed']
    owner_path = base/'candidate_layout_checks_001/owner.json'
    owner = json.loads(owner_path.read_text())
    deadline = min(owner['deadline_uptime'], json.loads((route/'owner.json').read_text())['deadline_uptime'])
    assert deadline > time.clock_gettime(time.CLOCK_BOOTTIME)
    out.mkdir(exist_ok=False)
    save(out/'owner.json', dict(runner_pid=os.getpid(), started_utc=datetime.now(timezone.utc).isoformat(),
        original_owner=str(owner_path), deadline_uptime=deadline, total_budget_restarted=False,
        automatic_identical_retry=False))
    rules = ROOT/'build/timing450/pdk/sky130A/libs.tech/librelane'
    paths = [Path(__file__).resolve(), Path(OPENROAD), route/'assessment.json', route/'route.odb',
        route/'route.def', final, owner_path]
    paths += [rules/f'rules.openrcx.sky130A.{corner}.magic' for corner in ['min','nom','max']]
    pins = {str(p):sha(p) for p in paths}
    save(out/'input_manifest.json', dict(input_sha256=pins, scope=__doc__))
    cases = {}
    for corner in ['min','nom','max']:
        task = out/f'{corner}.tcl'
        spef = out/f'{corner}.spef'
        task.write_text(f'''read_db {route}/route.odb
set_thread_count 2
define_process_corner -ext_model_index 0 RCX_{corner.upper()}
extract_parasitics -ext_model_file {rules}/rules.openrcx.sky130A.{corner}.magic -corner 0
write_spef -coordinates {spef}
puts "PARENT_WIRE_RCX_COMPLETE_{corner}"
exit
''')
        with (out/f'{corner}.log').open('x') as log:
            child = subprocess.Popen([OPENROAD, '-exit', str(task)], stdout=log, stderr=subprocess.STDOUT,
                cwd=out, start_new_session=True)
            save(out/'status.json', dict(state='native_rcx_running', corner=corner, native_pid=child.pid,
                native_analog_jobs_added=0, release_qualified=False))
            try:
                code = child.wait(timeout=max(0, deadline-time.clock_gettime(time.CLOCK_BOOTTIME)))
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGTERM)
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL)
                    child.wait()
                save(out/'status.json', dict(state='timeout_inconclusive', corner=corner, release_qualified=False))
                return
        text = (out/f'{corner}.log').read_text()
        assert code == 0 and f'PARENT_WIRE_RCX_COMPLETE_{corner}' in text, text[-3000:]
        assert spef.exists() and '*RES' in spef.read_text()
        cases[corner] = dict(native_exit_code=code, spef=str(spef), spef_sha256=sha(spef))
    for p, digest in pins.items():
        assert sha(p) == digest, p
    artifacts = {str(p):sha(p) for p in out.iterdir() if p.is_file() and p.name not in ['status.json','owner.json']}
    save(out/'native_completion.json', dict(input_sha256=pins, artifacts=artifacts,
        cases=cases, current_parent_route_odb=str(route/'route.odb'),
        all_three_wire_rc_extractions_complete=True, macro_internals_included=False,
        generated_gds_fill_included=False, nonlinear_pin_capacitance_included=False,
        full_rc_qualified=False, physical_timing_qualified=False, release_qualified=False, adopted=False, scope=__doc__))
    save(out/'status.json', dict(state='parent_wire_rc_raw_terminal', release_qualified=False))
    print('Current parent-wire min/nom/max raw RC extraction completed; matching full-GDS loading and enclosure remain open.')


if __name__ == '__main__':
    main()
