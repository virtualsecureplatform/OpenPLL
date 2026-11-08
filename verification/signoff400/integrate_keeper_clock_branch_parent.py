"""Replace the digital definition in a fresh filled-parent copy and check full DRC."""
import argparse
import json
import os
from pathlib import Path
import re
import sys
import time
import klayout.db as k

from common_v3 import ROOT, save, sha, verify
from resources import identity, lease
from compiled_charge_v2 import execute
from assemble_selected_keeper_parent import signature
from audit_keeper_digital_macro_reuse import compare_cells

MASTER = 'IntegerPLL_ProgrammedCore'
MAGIC = Path('/nix/store/i68lxdmnc7422hvlabbmrhss4sqqkjzq-magic-vlsi-8.3.623/bin/magic')
PDK = Path('/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A')


def checked(path):
    value = json.loads(path.read_text())
    verify(value['input_sha256'])
    verify(value['artifacts'])
    return value


def replace(target, source):
    if target.dbu != source.dbu:
        raise ValueError('layout database grid mismatch')
    dst, src = target.cell(MASTER), source.cell(MASTER)
    if dst is None or src is None:
        raise ValueError('digital macro missing')
    refs = [(c.name, str(i.cell_inst)) for c in target.each_cell()
            for i in c.each_inst() if i.cell.name == MASTER]
    if len(refs) != 1:
        raise ValueError('exactly one parent reference required')
    before = {c.name: signature(target, c) for c in target.each_cell() if c.name != MASTER}
    mapping = {src.cell_index(): dst.cell_index()}
    copies = [(src, dst)]
    renamed = {}
    for cell in source.each_cell():
        if cell == src:
            continue
        existing = target.cell(cell.name)
        if existing is not None and signature(target, existing) == signature(source, cell):
            mapping[cell.cell_index()] = existing.cell_index()
            continue
        name = cell.name
        if existing is not None:
            name = 'openpll_clock1471__' + name
            if target.cell(name) is not None:
                raise ValueError('private cell collision')
            renamed[cell.name] = name
        new = target.create_cell(name)
        mapping[cell.cell_index()] = new.cell_index()
        copies.append((cell, new))
    layers = k.LayerMapping()
    layers.create_full(target, source)
    dst.clear()
    for src_cell, dst_cell in copies:
        dst_cell.copy_shapes(src_cell, layers)
        for inst in src_cell.each_inst():
            array = inst.cell_inst
            array.cell_index = mapping[array.cell_index]
            dst_cell.insert(array)
    return before, refs, renamed


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    os.sched_setaffinity(0, {28})
    os.environ.update(OMP_NUM_THREADS='1', OMP_THREAD_LIMIT='1', OPENBLAS_NUM_THREADS='1')
    save(output / 'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid())))
    base = ROOT / 'build/signoff400'
    parent = base / 'selected_keeper_checked_filled_parent_1147'
    physical = base / 'selected_keeper_clock_branch_layout_1459'
    candidate = base / 'selected_keeper_clock_branch_candidate_1452'
    try:
        p = checked(parent / 'assessment.json')
        a = checked(physical / 'assessment.json')
        checked(candidate / 'assessment.json')
        if not (p['assembled_drc_pass'] and p['assembled_lvs_pass']
                and a['digital_component_results']['diagnostic_physical_pass']):
            raise ValueError('checked original parent and digital component required')
        native = physical / 'candidate/signoff/assessment.json'
        n = json.loads(native.read_text())
        verify(n['sha256'])
        if n['sha256'].get(str(physical / 'candidate/route.odb')) != sha(candidate / 'route.odb'):
            raise ValueError('component checks use another ECO database')
        old_lef = base / 'prototype_v3_selected_route_019/digital.lef'
        new_lef = candidate / 'digital.lef'
        prefixes = [re.split(r'^\s*OBS\s*$', path.read_text(), flags=re.M) for path in (old_lef, new_lef)]
        if any(len(parts) != 2 for parts in prefixes) or prefixes[0][0] != prefixes[1][0]:
            raise ValueError('macro outline and every LEF pin declaration must remain exact')
        old_gds, new_gds = parent / 'assembly.gds', physical / 'candidate/signoff/route.gds'
        startup = PDK / 'libs.tech/magic/sky130A.magicrc'
        tech = PDK / 'libs.tech/magic/sky130A.tech'
        files = [Path(__file__).resolve(), parent / 'assessment.json', physical / 'assessment.json',
                 candidate / 'assessment.json', native, old_gds, new_gds, old_lef, new_lef,
                 Path(__file__).with_name('assemble_selected_keeper_parent.py'),
                 Path(__file__).with_name('audit_keeper_digital_macro_reuse.py'),
                 Path(sys.executable).resolve(), MAGIC, startup, tech]
        pins = {str(path): sha(path) for path in files}
        save(output / 'inputs.json', dict(input_sha256=pins, CPU=28, assembly_memory_GiB=4,
             DRC_memory_GiB=12, resource_queue_cap_s=86400, native_DRC_cap_s=3600,
             original_parent_modified=False, candidate_selected=False, release_ready=False))
        save(output / 'status.json', dict(state='building_isolated_parent_with_clock_ECO', release_ready=False))
        with lease(1, 4, time.clock_gettime(time.CLOCK_BOOTTIME) + 86400):
            target, source = k.Layout(), k.Layout()
            target.read(str(old_gds))
            source.read(str(new_gds))
            before, refs, renamed = replace(target, source)
            gds = output / 'assembly.gds'
            target.write(str(gds))
            result = k.Layout()
            result.read(str(gds))
            if any(result.cell(name) is None or signature(result, result.cell(name)) != digest
                   for name, digest in before.items()):
                raise ValueError('serialized parent or non-digital original cell changed')
            if any(c.is_ghost_cell() for c in result.each_cell()):
                raise ValueError('unresolved GDS definition')
            comparison = compare_cells(source, result, MASTER)
            if not comparison['all_recursive_layer_geometry_and_texts_match']:
                raise ValueError('integrated digital geometry/text differs from checked source')
            verify(pins)
            geometry = output / 'geometry.json'
            save(geometry, dict(**comparison, original_parent_reference=refs,
                 unchanged_original_cell_definitions=len(before), private_cell_renames=renamed,
                 all_other_original_cell_definitions_preserved=True, LEF_outline_and_pin_prefix_exact=True))
        # Keep assembly evidence separate from the pending native DRC result.
        save(output / 'assembly_receipt.json', dict(input_sha256=pins,
             artifacts={str(path): sha(path) for path in (gds, geometry)},
             isolated_digital_definition_replacement=True, selected=False,
             parent_DRC_LVS_density_and_model_qualified=False, release_ready=False))
        report, script = output / 'drc_errors.rpt', output / 'drc.tcl'
        script.write_text(f'''crashbackups stop
drc euclidean on
drc style drc(full)
drc on
snap internal
gds flatten true
gds read {{{gds}}}
load IntegerPLL_400MHz_PrototypeTop
select top cell
expand
drc catchup
set f [open {{{report}}} w]
set count 0
foreach {{why boxes}} [drc listall why] {{
 puts $f $why
 foreach box $boxes {{incr count; puts $f $box}}
}}
puts $f "MAGIC_DRC_RECTANGLES=$count"
close $f
quit -noprompt
''')
        pins.update({str(path): sha(path) for path in (gds, geometry, script, output / 'assembly_receipt.json')})
        save(output / 'status.json', dict(state='waiting_for_full_parent_DRC_resources', release_ready=False))
        with lease(1, 12, time.clock_gettime(time.CLOCK_BOOTTIME) + 86400):
            deadline = time.clock_gettime(time.CLOCK_BOOTTIME) + 3600
            os.environ['PDK_ROOT'] = str(PDK.parent)
            save(output / 'status.json', dict(state='checking_full_flat_parent_DRC', release_ready=False))
            execute([MAGIC, '-dnull', '-noconsole', '-rcfile', startup, script], output / 'native.log', deadline, 12)
        counts = re.findall(r'^MAGIC_DRC_RECTANGLES=(\d+)$', report.read_text(), re.M)
        if len(counts) != 1:
            raise ValueError('one completed full-parent DRC count required')
        verify(pins)
        save(output / 'assessment.json', dict(input_sha256=pins,
             artifacts={str(path): sha(path) for path in (gds, geometry, report, output / 'native.log')},
             all_other_original_cell_definitions_preserved=True, exact_checked_digital_geometry_integrated=True,
             full_parent_Magic_DRC_rectangles=int(counts[0]), full_parent_Magic_DRC_pass=int(counts[0]) == 0,
             parent_LVS_checked=False, parent_density_checked=False, parent_model_qualified=False,
             original_parent_modified=False, selected=False, release_ready=False))
        save(output / 'status.json', dict(state='isolated_clock_ECO_parent_DRC_assessed', release_ready=False))
    except BaseException as error:
        save(output / 'status.json', dict(state='stopped_without_qualification', reason=repr(error), release_ready=False))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output.resolve())
