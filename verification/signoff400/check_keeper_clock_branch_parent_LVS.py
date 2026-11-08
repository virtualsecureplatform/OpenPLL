"""Compare the fresh ECO parent against independently powered child/top netlists."""
import argparse
import json
import os
from pathlib import Path
import time

from common_v3 import ROOT, save, sha, verify
from resources import identity, lease
from compiled_charge_v2 import execute
from integrate_keeper_clock_branch_parent import MAGIC, PDK
import normalize_selected_keeper_body_aliases_v2 as body
from replay_prototype_parent_port_alias_lvs import normalize as parent_alias, NETGEN


def checked(path):
    value = json.loads(path.read_text())
    verify(value['input_sha256'])
    verify(value['artifacts'])
    return value


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    os.sched_setaffinity(0, {30})
    os.environ.update(OMP_NUM_THREADS='1', OMP_THREAD_LIMIT='1', OPENBLAS_NUM_THREADS='1', PDK_ROOT=str(PDK.parent))
    save(output / 'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid())))
    base = ROOT / 'build/signoff400'
    assembly = base / 'selected_keeper_clock_branch_parent_1471'
    physical = base / 'selected_keeper_clock_branch_layout_1459'
    old = base / 'selected_keeper_filled_parent_LVS_1145'
    old_alias = base / 'selected_keeper_filled_parent_alias_LVS_1146'
    try:
        deadline = time.clock_gettime(time.CLOCK_BOOTTIME) + 86400
        receipt = assembly / 'assembly_receipt.json'
        save(output / 'status.json', dict(state='waiting_for_closed_ECO_parent_geometry', release_ready=False))
        while not receipt.exists():
            state = json.loads((assembly / 'status.json').read_text())
            owner = json.loads((assembly / 'owner.json').read_text())
            if state['state'] == 'stopped_without_qualification' or identity(owner['pid']) != owner['birth']:
                raise RuntimeError('parent assembly stopped before completed geometry receipt')
            if time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:
                raise TimeoutError('parent assembly observation deadline')
            time.sleep(10)
        a = checked(receipt)
        p = checked(physical / 'assessment.json')
        if not a['isolated_digital_definition_replacement'] or not p['digital_component_results']['diagnostic_physical_pass']:
            raise ValueError('verified geometry replacement and checked digital component required')
        if a['input_sha256'].get(str(physical / 'assessment.json')) != sha(physical / 'assessment.json'):
            raise ValueError('assembled parent uses another digital component')
        gds = assembly / 'assembly.gds'
        original_extract = old / 'extract.tcl'
        original_compare = old_alias / 'compare.tcl'
        # Check the retained recipes through their own completed evidence first.
        checked(old / 'assessment.json')
        checked(old_alias / 'assessment.json')
        extraction = output / 'extraction'
        extraction.mkdir()
        script = output / 'extract.tcl'
        text = original_extract.read_text()
        for before, after in [(base / 'selected_keeper_rerouted_parent_fill_1143/assembly.gds', gds),
                              (old / 'extraction', extraction)]:
            if text.count(str(before)) != 1:
                raise ValueError('retained extraction recipe differs')
            text = text.replace(str(before), str(after))
        script.write_text(text)
        normalized = output / 'assembly_parent_alias_normalized.spice'
        compare = output / 'compare.tcl'
        text = original_compare.read_text()
        for before, after in [(old_alias / normalized.name, normalized),
                              (base / 'prototype_v3_selected_route_019/signoff/powered.v', physical / 'candidate/signoff/powered.v'),
                              (old_alias / 'compare.log', output / 'compare.log')]:
            if text.count(str(before)) != 1:
                raise ValueError('retained comparison recipe differs')
            text = text.replace(str(before), str(after))
        compare.write_text(text)
        files = [Path(__file__).resolve(), Path(body.__file__),
                 Path(__file__).with_name('replay_prototype_parent_port_alias_lvs.py'),
                 Path(__file__).with_name('integrate_keeper_clock_branch_parent.py'),
                 receipt, physical / 'assessment.json', old / 'assessment.json', old_alias / 'assessment.json',
                 gds, original_extract, original_compare, script, compare, MAGIC, Path(NETGEN),
                 PDK / 'libs.tech/magic/sky130A.magicrc', PDK / 'libs.tech/magic/sky130A.tech']
        for line in text.splitlines():
            fields = line.split()
            if fields and fields[0] == 'readnet' and fields[2] != str(normalized):
                files.append(Path(fields[2]))
            if fields and fields[0] == 'lvs':
                files.extend(Path(field) for field in fields if field.startswith('/') and field.endswith('.tcl'))
        pins = {str(path): sha(path) for path in files}
        save(output / 'inputs.json', dict(input_sha256=pins, CPU=30, memory_GiB=12,
             resource_queue_cap_s=86400, native_cap_s=3600, independent_ECO_powered_netlist_used=True,
             no_assumed_parent_aliases=True, selected=False, release_ready=False))
        save(output / 'status.json', dict(state='waiting_for_parent_LVS_resources', release_ready=False))
        with lease(1, 12, time.clock_gettime(time.CLOCK_BOOTTIME) + 86400):
            deadline = time.clock_gettime(time.CLOCK_BOOTTIME) + 3600
            save(output / 'status.json', dict(state='extracting_ECO_parent_connectivity', release_ready=False))
            execute([MAGIC, '-dnull', '-noconsole', '-rcfile', PDK / 'libs.tech/magic/sky130A.magicrc', script],
                    output / 'extract.log', deadline, 12)
            # Both transformations fail unless the new extraction itself supplies
            # the required exact-zero-ohm witnesses; no old net alias is assumed.
            body.CHILD = 'openpll_keeper1125__sky130_fd_sc_hs__inv_2'
            flattened, body_proof = body.normalize((output / 'assembly.spice').read_text(),
                'IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160')
            text, alias_proof = parent_alias(flattened)
            normalized.write_text(text)
            save(output / 'alias_proofs.json', dict(body=body_proof, parent=alias_proof))
            save(output / 'status.json', dict(state='comparing_independent_ECO_powered_references', release_ready=False))
            execute([NETGEN, '-batch', 'source', compare], output / 'native.log', deadline, 12)
        native, log = [(output / name).read_text() for name in ('native.log', 'compare.log')]
        records = json.loads((output / 'compare.json').read_text())
        if 'There were errors reading the setup file' in native or 'Error ' in native:
            raise ValueError('native LVS setup/runtime error')
        names = ['IntegerPLL_ProgrammedCore', 'IntegerPLL_BBPD',
                 'IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160']
        expanded = all(any(row.get('name') == [name, name]
                       and len(row.get('devices', [])) == 2
                       and all(sum(int(count) for _, count in side) > 0 for side in row['devices'])
                       for row in records) for name in names)
        clean = (records[-1].get('name') == ['IntegerPLL_400MHz_PrototypeTop'] * 2
                 and all(not row.get('badnets') and not row.get('badelements') and not row.get('properties') for row in records))
        unique = ('Final result: Circuits match uniquely.' in log and 'Property errors were found' not in log
                  and 'Top level cell failed pin matching' not in log)
        verify(pins)
        targets = [output / name for name in ('assembly.spice', 'assembly_parent_alias_normalized.spice',
                   'alias_proofs.json', 'extract.log', 'native.log', 'compare.log', 'compare.json')]
        save(output / 'assessment.json', dict(input_sha256=pins,
             artifacts={str(path): sha(path) for path in targets}, all_three_macros_expanded=expanded,
             all_records_without_discrepancies=clean, parent_LVS_match=unique and clean and expanded,
             independent_ECO_powered_netlist_used=True, original_extraction_preserved=True,
             exact_alias_witnesses_from_new_extraction=True, parent_DRC_inherited=False,
             timing_models_or_density_qualified=False, selected=False, release_ready=False))
        save(output / 'status.json', dict(state='isolated_ECO_parent_LVS_assessed', release_ready=False))
    except BaseException as error:
        save(output / 'status.json', dict(state='stopped_without_qualification', reason=repr(error), release_ready=False))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output.resolve())
