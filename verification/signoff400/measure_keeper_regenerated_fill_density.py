"""Measure completed ECO fill with stock tiles; retain the small-macro applicability stop."""
import argparse
import json
import os
from pathlib import Path
import time
from common_v3 import ROOT, save, sha, verify
from resources import identity, lease
from compiled_charge_v2 import execute
from integrate_keeper_clock_branch_parent import MAGIC
from review_prototype_small_macro_density import run as review


def completed(directory, deadline):
    owner = json.loads((directory / 'owner.json').read_text())
    while not (directory / 'assessment.json').exists():
        state = json.loads((directory / 'status.json').read_text())['state']
        if state == 'stopped_without_qualification' or identity(owner['pid']) != owner['birth']:
            raise RuntimeError('physical prerequisite stopped: ' + str(directory))
        if time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:
            raise TimeoutError('physical prerequisite observation deadline')
        time.sleep(10)
    result = json.loads((directory / 'assessment.json').read_text())
    verify(result['input_sha256'])
    verify(result['artifacts'])
    return result


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    os.sched_setaffinity(0, {28})
    os.environ.update(OMP_NUM_THREADS='1', OMP_THREAD_LIMIT='1', OPENBLAS_NUM_THREADS='1')
    save(output / 'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid())))
    base = ROOT / 'build/signoff400'
    source = base / 'selected_keeper_clock_branch_regenerated_fill_1476'
    drc, lvs = [base / name for name in ('selected_keeper_clock_branch_filled_parent_DRC_1477',
                                        'selected_keeper_clock_branch_filled_parent_LVS_1478')]
    try:
        save(output / 'status.json', dict(state='waiting_for_regenerated_parent_DRC_and_LVS', release_ready=False))
        deadline = time.clock_gettime(time.CLOCK_BOOTTIME) + 86400
        d, l = [completed(path, deadline) for path in (drc, lvs)]
        receipt = source / 'assessment.json'
        if (d.get('full_parent_Magic_DRC_pass') is not True or l.get('parent_LVS_match') is not True
                or l.get('all_three_macros_expanded') is not True
                or any(r['input_sha256'].get(str(receipt)) != sha(receipt) for r in (d, l))):
            raise ValueError('same regenerated filled parent must pass DRC and expanded LVS')
        a = json.loads(receipt.read_text())
        verify(a['input_sha256'])
        verify(a['artifacts'])
        private = ROOT / 'build/timing450/pdk/sky130A'
        method = private / 'libs.tech/magic/check_density.py'
        gds = source / 'assembly.gds'
        files = [receipt, drc / 'assessment.json', lvs / 'assessment.json', gds,
                 Path(__file__).resolve(), Path(__file__).with_name('review_prototype_small_macro_density.py'),
                 method, MAGIC, private / 'libs.tech/magic/sky130A.tech', private / 'libs.tech/magic/sky130A.magicrc']
        pins = {str(path): sha(path) for path in files}
        save(output / 'input_manifest.json', dict(input_sha256=pins,
             declared_die_nm=a['declared_parent_die_nm'], CPU=28, memory_GiB=12,
             native_cap_s=3600, resource_queue_cap_s=86400, release_ready=False))
        (output / 'IntegerPLL_400MHz_PrototypeTop.gds').symlink_to(gds)
        os.environ.update(PDK_ROOT=str(private.parent), PDK='sky130A',
                          PATH=str(MAGIC.parent) + os.pathsep + os.environ['PATH'])
        os.chdir(output)
        save(output / 'status.json', dict(state='waiting_for_density_resources', release_ready=False))
        with lease(1, 12, time.clock_gettime(time.CLOCK_BOOTTIME) + 86400):
            save(output / 'status.json', dict(state='measuring_stock_density_tiles', release_ready=False))
            exit_code = 0
            try:
                execute(['/usr/bin/python3', method, 'IntegerPLL_400MHz_PrototypeTop.gds'], output / 'density.log',
                        time.clock_gettime(time.CLOCK_BOOTTIME) + 3600, 12)
            except RuntimeError as error:
                if str(error) != f'compiled worker failed (1): {output / "density.log"}':
                    raise
                exit_code = 1
            # This reviewer requires complete native tiles, normal Magic exit,
            # and the explicit stock small-macro applicability stop. A crash or
            # incomplete/native failed measurement cannot produce its receipt.
            review(output, output / 'review')
        r = json.loads((output / 'review/assessment.json').read_text())
        verify(r['input_sha256'])
        verify(pins)
        save(output / 'assessment.json', dict(input_sha256=pins,
             artifacts={str(path): sha(path) for path in (output / 'density.log', output / 'review/assessment.json')},
             native_stock_wrapper_exit_code=exit_code, native_tile_measurement_completed=True,
             stock_wrapper_passed=False, raw_tiles=r['raw_tiles'], results=r['results'],
             global_density_limits_met=r['global_density_limits_met'], stepped_windows_available=False,
             chip_integration_density_qualified=False, physical_integrity_qualified=False, release_ready=False))
        save(output / 'status.json', dict(state='regenerated_fill_density_tiles_reviewed', release_ready=False))
    except BaseException as error:
        save(output / 'status.json', dict(state='stopped_without_qualification', reason=repr(error), release_ready=False))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output.resolve())
