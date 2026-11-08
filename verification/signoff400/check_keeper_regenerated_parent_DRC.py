"""Fresh full flat DRC of completed ECO fill; never inherit an unfilled pass."""
import argparse
import json
import os
from pathlib import Path
import re
import time
from common_v3 import ROOT, save, sha, verify
from resources import identity, lease
from compiled_charge_v2 import execute
from integrate_keeper_clock_branch_parent import MAGIC, PDK


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    os.sched_setaffinity(0, {28})
    os.environ.update(OMP_NUM_THREADS='1', OMP_THREAD_LIMIT='1', OPENBLAS_NUM_THREADS='1', PDK_ROOT=str(PDK.parent))
    save(output / 'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid())))
    source = ROOT / 'build/signoff400/selected_keeper_clock_branch_regenerated_fill_1476'
    try:
        deadline = time.clock_gettime(time.CLOCK_BOOTTIME) + 86400
        receipt = source / 'assessment.json'
        owner = json.loads((source / 'owner.json').read_text())
        birth = identity(owner['pid'])
        save(output / 'status.json', dict(state='waiting_for_completed_regenerated_fill', release_ready=False))
        while not receipt.exists():
            state = json.loads((source / 'status.json').read_text())['state']
            if state in ('failed', 'stopped_without_qualification') or birth is None or identity(owner['pid']) != birth:
                raise RuntimeError('fill producer stopped before completed receipt')
            if time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:
                raise TimeoutError('fill observation deadline')
            time.sleep(10)
        a = json.loads(receipt.read_text())
        verify(a['input_sha256'])
        verify(a['artifacts'])
        if not all(a.get(key) is True for key in ('fill_preparation_only', 'only_fill_purpose_layers_added',
                'all_original_parent_geometry_and_labels_preserved', 'unfilled_parent_DRC_pass', 'unfilled_parent_LVS_pass')):
            raise ValueError('completed fill over the DRC/LVS-clean ECO parent required')
        gds = source / 'assembly.gds'
        report, script = output / 'drc_errors.rpt', output / 'drc.tcl'
        original = ROOT / 'build/signoff400/selected_keeper_clock_branch_parent_1471/drc.tcl'
        text = original.read_text()
        for old, new in [(original.parent / 'assembly.gds', gds), (original.parent / 'drc_errors.rpt', report)]:
            if text.count(str(old)) != 1:
                raise ValueError('unchanged native DRC recipe required')
            text = text.replace(str(old), str(new))
        script.write_text(text)
        files = [receipt, gds, script, original, Path(__file__).resolve(),
                 Path(__file__).with_name('integrate_keeper_clock_branch_parent.py'), MAGIC,
                 PDK / 'libs.tech/magic/sky130A.magicrc', PDK / 'libs.tech/magic/sky130A.tech']
        pins = {str(path): sha(path) for path in files}
        save(output / 'inputs.json', dict(input_sha256=pins, CPU=28, memory_GiB=12,
             resource_queue_cap_s=86400, native_cap_s=3600, maximum_native_cases=1, release_ready=False))
        save(output / 'status.json', dict(state='waiting_for_regenerated_parent_DRC_resources', release_ready=False))
        with lease(1, 12, time.clock_gettime(time.CLOCK_BOOTTIME) + 86400):
            deadline = time.clock_gettime(time.CLOCK_BOOTTIME) + 3600
            save(output / 'status.json', dict(state='checking_regenerated_filled_parent_DRC', release_ready=False))
            execute([MAGIC, '-dnull', '-noconsole', '-rcfile', PDK / 'libs.tech/magic/sky130A.magicrc', script],
                    output / 'native.log', deadline, 12)
        counts = re.findall(r'^MAGIC_DRC_RECTANGLES=(\d+)$', report.read_text(), re.M)
        if len(counts) != 1:
            raise ValueError('completed full flat DRC count required')
        verify(pins)
        save(output / 'assessment.json', dict(input_sha256=pins,
             artifacts={str(path): sha(path) for path in (report, output / 'native.log')},
             full_parent_Magic_DRC_rectangles=int(counts[0]), full_parent_Magic_DRC_pass=int(counts[0]) == 0,
             regenerated_fill_included=True, unfilled_DRC_pass_inherited=False,
             parent_LVS_density_and_model_qualified=False, selected=False, release_ready=False))
        save(output / 'status.json', dict(state='regenerated_filled_parent_DRC_assessed', release_ready=False))
    except BaseException as error:
        save(output / 'status.json', dict(state='stopped_without_qualification', reason=repr(error), release_ready=False))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output.resolve())
