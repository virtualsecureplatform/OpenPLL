"""Observe the owned geometry producer, then convert and audit once, without retries."""
import json
import os
import sys
import time
from pathlib import Path

from runtime_common import ROOT, save, sha
from resources import identity
from compiled_charge_v2 import execute


def run():
    source = ROOT / 'build/signoff400/selected_corrected_full_RC_1671'
    owner = json.loads((source / 'owner.json').read_text())
    if identity(owner['pid']) != owner['birth']:
        raise ValueError('queue admission requires the verified live producer')
    scripts = [Path(__file__).with_name(name) for name in
               ['reexport_completed_RC_1680.py', 'audit_completed_RC_1681.py']]
    helpers = [Path(__file__).with_name(name) for name in
               ['native_device_identity.py', 'native_C_roundoff.py',
                'native_C_passivity_v2.py', 'audit_keeper_native_R_contraction.py',
                'compare_native_R_with_aliases.py', 'native_spice_comments.py']]
    pins = {str(p): sha(p) for p in [Path(__file__).resolve(), *scripts, *helpers,
                                    source / 'inputs.json', source / 'owner.json']}
    out = ROOT / 'build/signoff400/selected_completed_RC_check_queue_1683'
    out.mkdir(exist_ok=False)
    save(out / 'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid())))
    save(out / 'inputs.json', dict(input_sha256=pins, producer_identity=owner,
         automatic_identical_retry=False, geometry_extraction_invoked=False))
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME) + 43200
    try:
        while not (source / 'assessment.json').exists():
            state = json.loads((source / 'status.json').read_text())
            if state['state'] == 'stopped_without_qualification':
                raise RuntimeError('producer stopped: ' + repr(state))
            if identity(owner['pid']) != owner['birth']:
                raise RuntimeError('producer ended without a normal completion receipt')
            if time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:
                raise TimeoutError('observation deadline; producer is not cancelled or restarted')
            save(out / 'status.json', dict(state='waiting_for_verified_live_producer',
                 producer_pid=owner['pid'], release_ready=False))
            time.sleep(10)
        completed = []
        for script in scripts:
            for name, digest in pins.items():
                if sha(Path(name)) != digest:
                    raise ValueError('queued input changed: ' + name)
            save(out / 'status.json', dict(state='running_completed_only_check',
                 script=script.name, release_ready=False))
            execute([sys.executable, str(script)], out / (script.stem + '.log'),
                    time.clock_gettime(time.CLOCK_BOOTTIME) + 10800, 20)
            completed.append(script.name)
        audit = ROOT / 'build/signoff400/selected_completed_RC_electrical_audit_1681/assessment.json'
        result = json.loads(audit.read_text())
        save(out / 'assessment.json', dict(input_sha256=pins, completed_scripts=completed,
             electrical_checks_pass=result['electrical_checks_pass'],
             electrical_audit_sha256=sha(audit),
             coverage_and_wire_value_gates_pending=True,
             RC_export_fixed=False, release_ready=False))
        save(out / 'status.json', dict(state='queued_checks_completed',
             electrical_checks_pass=result['electrical_checks_pass'], additional_gates_pending=True))
    except BaseException as error:
        save(out / 'status.json', dict(state='stopped_without_qualification', reason=repr(error)))
        raise


if __name__ == '__main__':
    run()
