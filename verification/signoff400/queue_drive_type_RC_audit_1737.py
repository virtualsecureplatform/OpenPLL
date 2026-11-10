"""Wait for the owned full producer, then audit its completed output once."""
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
    source = base / 'selected_drive_type_full_RC_1734'
    owner = json.loads((source / 'owner.json').read_text())
    if identity(owner['pid']) != owner['birth']:
        raise ValueError('queue admission requires the live full producer')
    script = Path(__file__).with_name('audit_drive_type_full_RC_1736.py')
    helpers = ['native_C_roundoff.py', 'native_C_passivity_v2.py',
               'native_physical_connections.py', 'native_wire_values.py',
               'native_RC_coverage_v2.py', 'native_device_identity.py',
               'audit_keeper_native_R_contraction.py', 'compare_native_R_with_aliases.py',
               'audit_completed_RC_1681.py', 'native_spice_comments.py']
    paths = [script, Path(__file__).resolve(), source / 'owner.json',
             *(Path(__file__).with_name(n) for n in helpers)]
    pins = {str(p): sha(p) for p in paths}
    out = base / 'selected_drive_type_RC_check_queue_1737'
    out.mkdir(exist_ok=False)
    save(out / 'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid())))
    save(out / 'inputs.json', dict(input_sha256=pins, source_identity=owner,
         automatic_identical_retry=False, geometry_extraction_invoked=False))
    try:
        deadline = time.clock_gettime(time.CLOCK_BOOTTIME) + 50000
        while not (source / 'assessment.json').exists():
            state = json.loads((source / 'status.json').read_text())
            if state['state'] == 'stopped_without_qualification':
                raise RuntimeError('producer failed: ' + repr(state))
            if identity(owner['pid']) != owner['birth']:
                raise RuntimeError('producer ended without a completion receipt')
            if time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:
                raise TimeoutError('observation deadline; producer not cancelled')
            save(out / 'status.json', dict(state='waiting_for_verified_live_full_producer'))
            time.sleep(10)
        for name, digest in pins.items():
            if sha(name) != digest:
                raise ValueError('queued input changed: ' + name)
        save(out / 'status.json', dict(state='running_completed_only_full_RC_audit'))
        execute([sys.executable, str(script)], out / 'audit.log',
                time.clock_gettime(time.CLOCK_BOOTTIME) + 12600, 20)
        receipt = base / 'selected_drive_type_full_RC_audit_1736/assessment.json'
        record = json.loads(receipt.read_text())
        save(out / 'assessment.json', dict(input_sha256=pins,
             full_audit_receipt_sha256=sha(receipt),
             all_full_RC_checks_pass=record['all_full_RC_checks_pass'],
             qualification_review_pending=True, RC_export_fixed=False, release_ready=False))
        save(out / 'status.json', dict(state='full_RC_audit_complete_review_pending',
             all_full_RC_checks_pass=record['all_full_RC_checks_pass']))
    except BaseException as error:
        save(out / 'status.json', dict(state='stopped_without_qualification', reason=repr(error)))
        raise


if __name__ == '__main__':
    run()
