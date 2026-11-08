"""Prepare an unqualified literal ECO model only after flat LVS and mask checks."""
import argparse
import json
import os
from pathlib import Path
import time
from common_v3 import ROOT, save, sha, verify
from resources import identity, lease
from prepare_keeper_flat_native_v2 import normalize


def completed(directory, deadline):
    owner = json.loads((directory / 'owner.json').read_text())
    while not (directory / 'assessment.json').exists():
        state = json.loads((directory / 'status.json').read_text())['state']
        if state == 'stopped_without_qualification' or identity(owner['pid']) != owner['birth']:
            raise RuntimeError('prerequisite stopped before completion: ' + str(directory))
        if time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:
            raise TimeoutError('completed evidence observation deadline')
        time.sleep(10)
    value = json.loads((directory / 'assessment.json').read_text())
    verify(value['input_sha256'])
    verify(value['artifacts'])
    return value


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    os.sched_setaffinity(0, {28})
    save(output / 'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid())))
    base = ROOT / 'build/signoff400'
    flat = base / 'selected_keeper_clock_parent_flat_C_1482'
    lvs = base / 'selected_keeper_clock_parent_flat_C_LVS_1484'
    masks = base / 'selected_keeper_clock_parent_flat_masks_1486'
    try:
        save(output / 'status.json', dict(state='waiting_for_ECO_flat_LVS_and_masks', release_ready=False))
        deadline = time.clock_gettime(time.CLOCK_BOOTTIME) + 86400
        r, l, m = [completed(directory, deadline) for directory in (flat, lvs, masks)]
        receipt = flat / 'assessment.json'
        if (l.get('unique_device_LVS_match') is not True or l.get('all_records_without_discrepancies') is not True
                or any(record['input_sha256'].get(str(receipt)) != sha(receipt) for record in (l, m))
                or any(m.get(key) is not True for key in ('all_conductor_masks_preserved',
                    'all_checked_active_selectors_preserved', 'diode_marker_on_active_diff_preserved',
                    'poly_diff_channel_region_preserved'))):
            raise ValueError('same flat export requires unique device LVS and preserved electrical masks')
        source = flat / 'capacitance.spice'
        names = ('prepare_keeper_flat_native_v2.py', 'prototype_native_literal_templates.py',
                 'prototype_xyce_resistor_translation.py', 'native_spice_comments.py',
                 'audit_hierarchical_capacitance.py')
        files = [directory / 'assessment.json' for directory in (flat, lvs, masks)]
        files += [source, Path(__file__).resolve(), *[Path(__file__).with_name(name) for name in names]]
        pins = {str(path): sha(path) for path in files}
        save(output / 'inputs.json', dict(input_sha256=pins, CPU=28, memory_GiB=12,
             native_analog_simulation_requested=False, release_ready=False))
        save(output / 'status.json', dict(state='normalizing_literal_ECO_devices_and_nonnegative_C', release_ready=False))
        with lease(1, 12, time.clock_gettime(time.CLOCK_BOOTTIME) + 86400):
            model, nodes, metrics = normalize(source.read_text())
            if metrics['source_counts'].get('X', 0) <= 0 or metrics['nonzero_C_preserved'] <= 0:
                raise ValueError('nonempty checked device and capacitance model required')
            target = output / 'model.spice'
            mapping = output / 'nodes.json'
            target.write_text(model)
            save(mapping, nodes)
        verify(pins)
        save(output / 'assessment.json', dict(input_sha256=pins,
             artifacts={str(path): sha(path) for path in (target, mapping)}, **metrics,
             expected_primitive_count_inferred_from_unchanged_old_layout=False,
             independent_flat_device_LVS_match=True, electrically_active_masks_preserved=True,
             constant_C_nonnegative=True, constant_C_PSD_by_nonnegative_branch_energy=True,
             distributed_wire_R_included=False, spatial_endpoint_attachment_applied=False,
             only_zero_C_cards_omitted=True, corrected_backend_correlation_complete=False,
             internal_wire_RC_timing_updated=False, native_simulation_allowed=False,
             selected=False, model_qualified=False, release_ready=False))
        save(output / 'status.json', dict(state='ECO_literal_reference_prepared_unqualified', release_ready=False))
    except BaseException as error:
        save(output / 'status.json', dict(state='stopped_without_qualification', reason=repr(error), release_ready=False))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output.resolve())
