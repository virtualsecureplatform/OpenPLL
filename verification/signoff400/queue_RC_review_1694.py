"""Run the physical-connection and final evidence review after the remaining gates."""
import json
import os
import sys
import time
from pathlib import Path
from runtime_common import ROOT, save, sha
from resources import identity
from compiled_charge_v2 import execute


def run():
    base = ROOT / 'build/signoff400'
    previous = base / 'selected_remaining_RC_gates_1688'
    owner = json.loads((previous / 'owner.json').read_text())
    if identity(owner['pid']) != owner['birth']:
        raise ValueError('admission requires the live predecessor controller')
    scripts = [Path(__file__).with_name(n) for n in
               ['review_completed_RC_1693.py']]
    helpers = [Path(__file__).with_name(n) for n in
               ['native_physical_connections.py', 'native_device_identity.py',
                'audit_completed_RC_1681.py', 'audit_keeper_native_R_contraction.py']]
    pins = {str(p): sha(p) for p in [*scripts, *helpers, Path(__file__).resolve()]}
    out = base / 'selected_RC_review_queue_1694'
    out.mkdir(exist_ok=False)
    save(out / 'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid())))
    save(out / 'inputs.json', dict(input_sha256=pins, predecessor_identity=owner,
         automatic_identical_retry=False))
    try:
        deadline = time.clock_gettime(time.CLOCK_BOOTTIME) + 54000
        while not (previous / 'assessment.json').exists():
            status = json.loads((previous / 'status.json').read_text())
            if status['state'] == 'stopped_without_qualification':
                raise RuntimeError('predecessor failed: ' + repr(status))
            if identity(owner['pid']) != owner['birth']:
                raise RuntimeError('predecessor ended without a completion receipt')
            if time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:
                raise TimeoutError('observation deadline; no producer cancelled')
            save(out / 'status.json', dict(state='waiting_for_verified_live_check_queue'))
            time.sleep(10)
        for script in scripts:
            for name, digest in pins.items():
                if sha(Path(name)) != digest:
                    raise ValueError('queued gate input changed: ' + name)
            save(out / 'status.json', dict(state='running_completed_only_gate', script=script.name))
            execute([sys.executable, str(script)], out / (script.stem + '.log'),
                    time.clock_gettime(time.CLOCK_BOOTTIME) + 7200, 12)
        records = [base / n / 'assessment.json' for n in
                   ['selected_completed_RC_review_1693']]
        save(out / 'assessment.json', dict(input_sha256=pins,
             gate_receipts={str(p): sha(p) for p in records},
             gates_executed=True, qualification_review_pending=True,
             RC_export_fixed=False, release_ready=False))
        save(out / 'status.json', dict(state='remaining_gates_complete_review_pending'))
    except BaseException as error:
        save(out / 'status.json', dict(state='stopped_without_qualification', reason=repr(error)))
        raise


if __name__ == '__main__':
    run()
