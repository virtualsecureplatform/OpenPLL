"""Remove only parent fill in a fresh ECO diagnostic, then run full flat DRC."""
import argparse
import json
import os
from pathlib import Path
import re
import time
import klayout.db as k
from common_v3 import ROOT, save, sha, verify
from resources import identity, lease
from compiled_charge_v2 import execute
from assemble_selected_keeper_parent import signature
from integrate_keeper_clock_branch_parent import MAGIC, PDK


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    os.sched_setaffinity(0, {28})
    os.environ.update(OMP_NUM_THREADS='1', OMP_THREAD_LIMIT='1', OPENBLAS_NUM_THREADS='1', PDK_ROOT=str(PDK.parent))
    save(output / 'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid())))
    source = ROOT / 'build/signoff400/selected_keeper_clock_branch_parent_1471'
    try:
        receipt = source / 'assessment.json'
        a = json.loads(receipt.read_text())
        verify(a['input_sha256'])
        verify(a['artifacts'])
        if a.get('full_parent_Magic_DRC_rectangles') != 2592:
            raise ValueError('predeclared failed filled-parent control required')
        files = [receipt, source / 'assembly.gds', Path(__file__).resolve(),
                 Path(__file__).with_name('assemble_selected_keeper_parent.py'),
                 Path(__file__).with_name('integrate_keeper_clock_branch_parent.py'), MAGIC,
                 PDK / 'libs.tech/magic/sky130A.magicrc', PDK / 'libs.tech/magic/sky130A.tech']
        pins = {str(path): sha(path) for path in files}
        save(output / 'status.json', dict(state='removing_only_parent_fill_instances', release_ready=False))
        with lease(1, 2, time.clock_gettime(time.CLOCK_BOOTTIME) + 86400):
            layout = k.Layout()
            layout.read(str(source / 'assembly.gds'))
            top = layout.cell('IntegerPLL_400MHz_PrototypeTop')
            names = {'PROTOTYPE_PARENT_DENSITY_FILL', 'PROTOTYPE_PARENT_METAL5_FILL'}
            before = {c.name: signature(layout, c) for c in layout.each_cell() if c != top}
            def inst(i):
                return i.cell.name, str(i.cplx_trans), str(i.a), str(i.b), i.na, i.nb
            retained = sorted(inst(i) for i in top.each_inst() if i.cell.name not in names)
            removed = []
            for i in list(top.each_inst()):
                if i.cell.name in names:
                    removed.append(inst(i))
                    i.delete()
            if sorted(row[0] for row in removed) != sorted(names):
                raise ValueError('one instance per declared parent-fill domain required')
            expected = signature(layout, top)
            gds = output / 'assembly.gds'
            layout.write(str(gds))
            restored = k.Layout()
            restored.read(str(gds))
            top = restored.cell('IntegerPLL_400MHz_PrototypeTop')
            if (signature(restored, top) != expected or sorted(inst(i) for i in top.each_inst()) != retained
                    or any(signature(restored, restored.cell(name)) != digest for name, digest in before.items())):
                raise ValueError('geometry other than declared fill instances changed')
        save(output / 'assembly_receipt.json', dict(input_sha256=pins,
             artifacts={str(gds): sha(gds)}, only_parent_fill_instances_removed=True,
             all_macro_cell_definitions_preserved=True, removed_instances=removed,
             fill_regeneration_required=True, selected=False, release_ready=False))
        script, report = output / 'drc.tcl', output / 'drc_errors.rpt'
        # Keep the same native DRC recipe; change only its input/output paths.
        original = source / 'drc.tcl'
        text = original.read_text()
        for before_path, after_path in [(source / 'assembly.gds', gds), (source / 'drc_errors.rpt', report)]:
            if text.count(str(before_path)) != 1:
                raise ValueError('same DRC recipe required')
            text = text.replace(str(before_path), str(after_path))
        script.write_text(text)
        pins.update({str(path): sha(path) for path in (original, gds, script, output / 'assembly_receipt.json')})
        save(output / 'inputs.json', dict(input_sha256=pins, CPU=28, memory_GiB=12,
             native_cap_s=3600, resource_queue_cap_s=86400, maximum_native_cases=1,
             automatic_identical_retry=False, release_ready=False))
        save(output / 'status.json', dict(state='waiting_for_unfilled_parent_DRC_resources', release_ready=False))
        with lease(1, 12, time.clock_gettime(time.CLOCK_BOOTTIME) + 86400):
            deadline = time.clock_gettime(time.CLOCK_BOOTTIME) + 3600
            save(output / 'status.json', dict(state='checking_unfilled_parent_DRC', release_ready=False))
            execute([MAGIC, '-dnull', '-noconsole', '-rcfile', PDK / 'libs.tech/magic/sky130A.magicrc', script],
                    output / 'native.log', deadline, 12)
        counts = re.findall(r'^MAGIC_DRC_RECTANGLES=(\d+)$', report.read_text(), re.M)
        if len(counts) != 1:
            raise ValueError('completed DRC count required')
        verify(pins)
        save(output / 'assessment.json', dict(input_sha256=pins,
             artifacts={str(path): sha(path) for path in (gds, report, output / 'native.log')},
             only_parent_fill_instances_removed=True, full_parent_Magic_DRC_rectangles=int(counts[0]),
             full_parent_Magic_DRC_pass=int(counts[0]) == 0, source_filled_DRC_rectangles=2592,
             stale_fill_is_sole_observed_DRC_cause=int(counts[0]) == 0,
             fill_regeneration_required=True, parent_LVS_density_or_model_qualified=False,
             selected=False, release_ready=False))
        save(output / 'status.json', dict(state='unfilled_parent_DRC_assessed', release_ready=False))
    except BaseException as error:
        save(output / 'status.json', dict(state='stopped_without_qualification', reason=repr(error), release_ready=False))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output.resolve())
