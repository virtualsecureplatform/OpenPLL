#!/usr/bin/env python3
"""Read-only monitoring attachment; never start/restart a native simulator."""
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
from compile_local_C_operators_v2 import digest, save
from record_qualification_progress_045 import process


def prefix(path):
    if not path.exists():
        return None
    raw = path.read_bytes()
    complete = raw[:raw.rfind(b'\n')+1].decode().splitlines()
    if not complete:
        return None
    assert complete[0].split() == ['Index', 'TIME', 'V(PLLOUT)', 'I(VVPWR)']
    rows, kept = [], [complete[0]]
    for line in complete[1:]:
        if not line.strip():
            continue
        if 'End of Xyce(TM) Simulation' in line:
            break
        fields = line.split()
        assert len(fields) == 4 and int(fields[0]) == len(rows)
        row = tuple(map(float, fields[1:]))
        assert all(math.isfinite(value) for value in row)
        rows.append(row)
        kept.append(line)
        if len(rows) == 2:
            return '\n'.join(kept)+'\n', rows
    return None


def main():
    root = Path(__file__).resolve().parents[2]
    base = root / 'build/timing400/release_001'
    recovery = base / 'DCO_gear_foreground_recovery_001'
    owner = json.loads((recovery / 'owner.json').read_text())
    deadline = owner['deadline_uptime']
    point = base / 'DCO_domain_nom_tt27_c0_f247_80ns_wire_preconditioned_gear_002'
    out = base / 'pending_Gear_DCO_monitor_001'
    out.mkdir(exist_ok=False)
    observer = Path(__file__).with_name('observe_DCO_native_progress.py').resolve()
    save(out / 'owner.json', dict(runner_pid=os.getpid(),
        started_utc=datetime.now(timezone.utc).isoformat(), deadline_uptime=deadline,
        source_recovery_pid=owner['runner_pid'], native_process_started_or_retried=False,
        input_sha256={str(p): digest(p) for p in (Path(__file__).resolve(), observer, recovery / 'owner.json')}))
    child = None
    while time.clock_gettime(time.CLOCK_BOOTTIME) < deadline:
        launch = point / 'launch.json'
        state_path = point / 'status.json'
        if launch.exists() and state_path.exists():
            launched = json.loads(launch.read_text())
            state = json.loads(state_path.read_text())
            identity = process(launched['pid'])
            if identity['live'] and identity['argv'][-1] == str(point / 'point.cir') and state.get('native_pid') == launched['pid']:
                with (out / 'observer.log').open('x') as log:
                    child = subprocess.Popen([sys.executable, str(observer), '--point', str(point),
                        '--native-pid', str(launched['pid']), '--output',
                        str(base / 'DCO_Gear_runtime_observer_001')], cwd=root,
                        stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                save(out / 'observer_owner.json', dict(observer_pid=child.pid,
                    source_native_identity=identity, deadline_uptime=deadline))
                break
        if not process(owner['runner_pid'])['live']:
            save(out / 'status.json', dict(state='source_recovery_terminal_before_attachment',
                native_process_changed=False, release_qualified=False))
            return
        save(out / 'status.json', dict(state='waiting_for_native_Gear_launch',
            source_recovery_live=True, deadline_uptime=deadline, release_qualified=False))
        time.sleep(min(5, max(.01, deadline-time.clock_gettime(time.CLOCK_BOOTTIME))))
    if child is None:
        save(out / 'status.json', dict(state='deadline_before_observer_attachment', release_qualified=False))
        return
    reference_path = base / 'DCO_domain_nom_tt27_c0_f247_80ns_wire_preconditioned_002/retained_stock_first_step.prn'
    reference = prefix(reference_path)
    assert reference is not None
    compared = False
    while child.poll() is None and time.clock_gettime(time.CLOCK_BOOTTIME) < deadline:
        if not compared:
            current = prefix(Path(str(point / 'point.cir')+'.prn'))
            if current is not None:
                original_text, old = reference
                current_text, new = current
                (out / 'retained_stock_prefix.prn').write_text(original_text)
                (out / 'retained_Gear_prefix.prn').write_text(current_text)
                same_grid = [row[0] for row in old] == [row[0] for row in new]
                dv = max(abs(a[1]-b[1]) for a, b in zip(old, new)) if same_grid else None
                di = max(abs(a[2]-b[2]) for a, b in zip(old, new)) if same_grid else None
                save(out / 'first_step_comparison.json', dict(reference_sha256=digest(reference_path),
                    common_time_grid=same_grid, source_time_s=[row[0] for row in old],
                    Gear_time_s=[row[0] for row in new], maximum_voltage_difference_V=dv,
                    maximum_supply_current_difference_A=di,
                    within_existing_first_step_thresholds=(dv <= 1e-6 and di <= 1e-10) if same_grid else None,
                    integration_method_differs=True, native_verdict_changed=False,
                    frequency_or_numerical_domain_qualified=False, release_qualified=False))
                compared = True
        save(out / 'status.json', dict(state='read_only_Gear_observer_attached',
            observer_pid=child.pid, first_step_comparison_recorded=compared,
            deadline_uptime=deadline, release_qualified=False))
        time.sleep(min(10, max(.01, deadline-time.clock_gettime(time.CLOCK_BOOTTIME))))
    if child.poll() is None:
        child.terminate()
        child.wait(timeout=5)
    save(out / 'assessment.json', dict(observer_exit=child.returncode,
        first_step_comparison_recorded=compared, native_process_started_or_retried=False,
        source_native_verdict_not_inferred=True, release_qualified=False))


if __name__ == '__main__':
    main()
