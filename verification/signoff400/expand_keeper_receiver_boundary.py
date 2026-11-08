"""Retain every primitive incident to a selected receiver cut, without clamping it."""
import argparse
import json
import os
import time
from pathlib import Path
from common_v3 import save, sha, verify
from export_keeper_conditional_DCO_v2 import partition
from native_spice_comments import strip_floating_annotation
from resources import lease


def expand(text, selected, receiver):
    added = set()
    for raw in text.splitlines():
        f = strip_floating_annotation(raw).split()
        if not f or not f[0].startswith('X'):
            continue
        end = next((i for i, value in enumerate(f) if '=' in value), len(f)) - 1
        if receiver in f[1:end] and f[0] not in selected:
            added.add(f[0])
    if not added:
        raise ValueError('no omitted receiver loads to expand')
    model, interface = partition(text, selected | added, free_outputs=['PLLOUT'])
    if receiver not in interface['interior_nodes'] or receiver in interface['boundary_ports']:
        raise ValueError('receiver node did not become an internal unknown')
    return model, interface, sorted(added)


def run(flat, conditional, receiver, output):
    if output.exists():
        raise FileExistsError(output)
    source = flat / 'capacitance.spice'
    receipt = conditional / 'assessment.json'
    previous = json.loads(receipt.read_text())
    verify(previous['artifacts'])
    if previous['input_sha256'].get(str(source)) != sha(source):
        raise ValueError('same physical extraction required')
    paths = [source, receipt, conditional / 'interface.json', Path(__file__).resolve()]
    paths += [Path(__file__).with_name(n) for n in ['export_keeper_conditional_DCO_v2.py', 'native_spice_comments.py', 'audit_keeper_DCO_driver_C_cut.py']]
    pins = {str(p): sha(p) for p in paths}
    old = json.loads((conditional / 'interface.json').read_text())
    if receiver not in old['externally_driven_ports']:
        raise ValueError('receiver must be an existing prescribed boundary')
    os.sched_setaffinity(0, {29})
    with lease(1, 8, time.clock_gettime(time.CLOCK_BOOTTIME) + 7200):
        model, interface, added = expand(source.read_text(), set(old['selected_primitive_names']), receiver)
        if not set(old['interior_nodes']) <= set(interface['interior_nodes']):
            raise ValueError('previous internal unknown became prescribed')
        verify(pins)
        output.mkdir(parents=True, exist_ok=False)
        (output / 'conditional.spice').write_text(model)
        save(output / 'interface.json', interface)
        save(output / 'assessment.json', dict(input_sha256=pins, artifacts={str(p): sha(p) for p in [output / 'conditional.spice', output / 'interface.json']},
             selected_primitive_count=len(interface['selected_primitive_names']), added_receiver_primitives=added,
             receiver_internal_unknown=receiver, receiver_no_longer_prescribed=True,
             PLLOUT_is_observation_only_and_not_externally_driven=True,
             no_omitted_branch_touches_interior=True, previous_internal_unknowns_preserved=True,
             all_retained_cards_unchanged=True, new_prescribed_boundaries=sorted(set(interface['externally_driven_ports']) - set(old['externally_driven_ports'])),
             environment_validated=False, native_execution_complete=False, changed_controller_prediction_qualified=False,
             model_qualified=False, release_ready=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ['flat', 'conditional', 'output']:
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--receiver', required=True)
    args = parser.parse_args()
    run(args.flat.resolve(), args.conditional.resolve(), args.receiver, args.output.resolve())
