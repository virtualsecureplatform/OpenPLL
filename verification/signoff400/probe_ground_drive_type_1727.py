"""Copy-only ground-driver diagnosis; no partial resistor model is accepted."""
import argparse
import json
import os
import re
import shutil
import time
from pathlib import Path
from runtime_common import ROOT, save, sha
from resources import identity, lease
from compiled_charge_v2 import execute
from replay_keeper_flat_signed_C import TECH
from extract_keeper_flat_geometry_C import FLAT


def run(driver):
    label = 'driver_1728' if driver else 'original_1727'
    out = ROOT / ('build/signoff400/selected_ground_copy_' + label)
    out.mkdir(exist_ok=False)
    save(out / 'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid())))
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME) + 5400
    try:
        engine = ROOT / 'build/tools/magic_drive_type_1726'
        owner = json.loads((engine / 'owner.json').read_text())
        save(out / 'status.json', dict(state='waiting_for_live_copy_diagnostic_build'))
        while not (engine / 'assessment.json').exists():
            if identity(owner['pid']) != owner['birth']:
                raise RuntimeError('diagnostic build ended without completion')
            if json.loads((engine / 'status.json').read_text())['state'] == 'stopped_without_qualification':
                raise RuntimeError('diagnostic build failed')
            if time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:
                raise TimeoutError('copy diagnostic admission deadline')
            time.sleep(5)
        receipt = engine / 'assessment.json'; record = json.loads(receipt.read_text())
        binary = engine / 'install/bin/magic'; library = engine / 'install/lib/magic/tcl/tclmagic.so'
        for p in [binary, library]:
            if record['artifacts'][str(p)] != sha(p):
                raise ValueError('native diagnostic artifact changed')
        source = ROOT / 'build/signoff400/selected_keeper_contact_corrected_C_1573'
        source_receipt = source / 'assessment.json'; sr = json.loads(source_receipt.read_text())
        gds, ext = source / 'flat.gds', source / (FLAT + '.ext')
        for p in [gds, ext]:
            if sr['artifacts'][str(p)] != sha(p):
                raise ValueError('checked source changed')
        shutil.copyfile(ext, out / ext.name)
        rc = out / 'minimal.magicrc'
        rc.write_text(f'tech load {{{TECH}}}\ndrc off\ncrashbackups disable\nlocking disable\n')
        script = out / 'run.tcl'
        script.write_text(f'''cd {{{out}}}
if {{[catch {{
gds read {{{gds}}}
load {FLAT}
select top cell
extract style ngspice()
extract no resistance
extresist simplify off
extresist threshold 0
extresist include VGND
extresist all
}} error]}} {{puts stderr $error;exit 1}}
quit -noprompt
''')
        paths = [receipt, source_receipt, binary, library, gds, ext, TECH, rc, script, Path(__file__).resolve()]
        pins = {str(p): sha(p) for p in paths}
        save(out / 'inputs.json', dict(input_sha256=pins, copy_seed_from_driver=driver,
             scope='only the original VGND conductor; return immediately after geometry copy',
             copy_only_diagnostic=True, R_network_generation_skipped=True,
             maximum_native_cases=1, automatic_identical_retry=False, native_cap_s=2400,
             CPU=29 if driver else 28, memory_GiB=16, RC_export_fixed=False))
        os.sched_setaffinity(0, {29 if driver else 28})
        env = ['env', '-u', 'OPENPLL_RC_COPY_FROM_DRIVER', 'OPENPLL_RC_NATIVE_CAPS=1',
               'OPENPLL_RC_EXPLICIT_COUPLING=1', 'OPENPLL_RC_ZERO_JUNCTION=1',
               'OPENPLL_RC_COPY_TRACE=1', 'OPENPLL_RC_COPY_PREFLIGHT_ONLY=1']
        if driver:
            env.append('OPENPLL_RC_COPY_FROM_DRIVER=1')
        with lease(1, 16, deadline):
            save(out / 'status.json', dict(state='native_ground_copy_diagnostic_running'))
            execute([*env, str(binary), '-nowrapper', '-dnull', '-noconsole', '-rcfile', str(rc), str(script)],
                    out / 'native.log', min(deadline, time.clock_gettime(time.CLOCK_BOOTTIME) + 2400), 16)
        traces = [line for line in (out / 'native.log').read_text().splitlines()
                  if line.startswith('OPENPLL_RC_COPY_TRACE ')]
        ends = [line for line in traces if 'stage=end ' in line]
        if len(ends) != 1:
            raise ValueError('exactly one completed copy-stage diagnostic required')
        found = re.search(r'expected=(\S+) found_left=(\S+) found_right=(\S+)', ends[0])
        if not found:
            raise ValueError('native type observation required')
        for name, digest in pins.items():
            if sha(name) != digest:
                raise ValueError('diagnostic input changed')
        save(out / 'assessment.json', dict(input_sha256=pins,
             artifacts={str(out / 'native.log'): sha(out / 'native.log')},
             copy_seed_from_driver=driver, completed_copy_stage_observations=traces,
             driver_type_present_after_copy=found[1] in [found[2], found[3]],
             early_return_was_intentional=True, R_network_generation_skipped=True,
             native_RC_model_qualified=False, RC_export_fixed=False, release_ready=False))
        save(out / 'status.json', dict(state='copy_stage_diagnostic_complete'))
    except BaseException as error:
        save(out / 'status.json', dict(state='stopped_without_qualification', reason=repr(error)))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--driver', action='store_true')
    run(parser.parse_args().driver)
