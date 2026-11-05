#!/usr/bin/env python3
"""Preserve every native R vertex/branch and bind devices by physical geometry.

Emit unqualified wire primitives and device-connection metadata for subsequent
model assembly. Original junction parameters are retained as metadata; their
spatial distribution, capacitor weights and public boundaries remain open.
"""
from collections import Counter, defaultdict
from decimal import Decimal
import json
import math
from pathlib import Path
import shlex
import signal
import struct
import time
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT, sha, save


def f32(value):
    return struct.unpack('f', struct.pack('f', value))[0]


def main():
    base = ROOT/'build/timing400/release_001'
    owner = base/'distributed_RC_model_qualification_001/owner.json'
    left = json.loads(owner.read_text())['deadline_uptime']-time.clock_gettime(time.CLOCK_BOOTTIME)
    assert left > 0
    signal.alarm(max(1, math.floor(left)))
    binding = base/'DCO_native_pointer_binding_index_001/assessment.json'
    original = base/'DCO_original_device_geometry_ids_003/assessment.json'
    retained = base/'DCO_retained_device_geometry_ids_002/assessment.json'
    assert verify(binding)['ambiguous_terminal_bindings'] == 0
    assert verify(original)['original_full_C_and_all_device_cards_preserved']
    assert verify(retained)['retained_R_C_and_all_device_cards_preserved']
    node_path = binding.parent/'nodes.json'
    bind_path = binding.parent/'device_bindings.json'
    original_path = original.parent/'device_geometry_index.json'
    retained_path = retained.parent/'device_geometry_index.json'
    nodes = json.loads(node_path.read_text())
    by_pointer, by_id, selected_groups = {}, {}, set()
    for row in nodes:
        group = row['private_id'].split('_')[2]
        key = (group, row['native_pointer'])
        assert key not in by_pointer and row['private_id'] not in by_id
        by_pointer[key] = row
        by_id[row['private_id']] = row
        selected_groups.add(group)
    originals = json.loads(original_path.read_text())
    afters = json.loads(retained_path.read_text())
    grouped = defaultdict(lambda: defaultdict(set))
    for row in json.loads(bind_path.read_text()):
        key = (row['model'], *row['point_internal'])
        grouped[key][row['terminal']].add(row['private_id'])
    source = base/'DCO_R_binding_trace_controls_001/trace'
    top = 'IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160'
    ext = source/(top+'.ext')
    parent = {}
    def canonical(n):
        parent.setdefault(n, n)
        while parent[n] != n:
            parent[n] = parent[parent[n]]
            n = parent[n]
        return n
    for line in ext.open():
        if line.startswith('equiv '):
            f = shlex.split(line)
            parent[canonical(f[1])] = canonical(f[2])
    def corresponds(private_nodes, original_card):
        return all(canonical(by_id[n]['original_conductor']) == canonical(old)
                   for n, old in zip(private_nodes, original_card))
    device_rows, used, unique_keys = {}, set(), set()
    fault_rejected = False
    for name, row in originals.items():
        other = afters[name]
        assert row['model'] == other['model'] and row['rectangle_internal'] == other['rectangle_internal']
        x, y, r, t = row['rectangle_internal']
        assert r == x+1 and t == y+1
        key = (row['model'], x, y)
        assert key not in unique_keys and key in grouped
        unique_keys.add(key)
        # Native terminal codes: GATE1 SOURCE2 DRAIN3 SUBS4. MSUBCKT writes
        # drain, gate, source, bulk; RSUBCKT writes source then drain.
        codes = [2, 3] if row['model'] == 'sky130_fd_pr__res_generic_po' else [3, 1, 2, 4]
        assert set(grouped[key]) == set(codes)
        assert all(len(grouped[key][code]) == 1 for code in codes)
        private_nodes = [next(iter(grouped[key][code])) for code in codes]
        original_card = row['original_card']
        assert corresponds(private_nodes, original_card)
        used.update(private_nodes)
        device_rows[name] = dict(model=row['model'], rectangle_internal=row['rectangle_internal'],
            private_terminals=private_nodes, native_terminal_codes=codes, original_card=original_card,
            junction_distribution_qualified=False)
        if not fault_rejected and len(codes) == 4 and canonical(original_card[0]) != canonical(original_card[1]):
            wrong = list(private_nodes)
            wrong[0], wrong[1] = wrong[1], wrong[0]
            assert not corresponds(wrong, original_card)
            fault_rejected = True
    assert unique_keys == grouped.keys() and len(device_rows) == 8620 and fault_rejected
    provenance = source/'R_provenance.log'
    res = source/(top+'.res.ext')
    out = base/'DCO_private_R_primitives_001'
    out.mkdir(exist_ok=False)
    printed, native_count = Counter(), 0
    seen, current, pending = set(), None, None
    minimum = None
    with (out/'wire_R_elements_unqualified.spice').open('x') as deck, (out/'branches.jsonl').open('x') as metadata:
        deck.write('* Unqualified native wire primitives; private node IDs; nominal native R.\n')
        with provenance.open() as stream:
            for line in stream:
                if line.startswith('BEGIN '):
                    f = shlex.split(line)
                    current = (f[1], f[2])
                    seen = set()
                elif line.startswith('BRANCH '):
                    f = line.split()
                    pending = f[1:]
                elif line.startswith('EDGE '):
                    f = line.split()
                    assert pending is not None and pending[0] == f[1] and pending[1] == f[2]
                    branch = pending[2]
                    pending = None
                    if current[0] not in selected_groups or branch in seen:
                        continue
                    seen.add(branch)
                    a, b = [by_pointer[f[1], p] for p in f[3:5]]
                    assert a['original_conductor'] == current[1] == b['original_conductor']
                    assert a['private_id'] != b['private_id']
                    milliohm = Decimal(f[5])
                    value = milliohm/1000
                    assert value > 0
                    minimum = value if minimum is None else min(minimum, value)
                    native_count += 1
                    deck.write(f'Rmesh_{native_count} {a["private_id"]} {b["private_id"]} {value}\n')
                    metadata.write(json.dumps(dict(index=native_count, native_group=f[1], native_branch=branch,
                        private_nodes=[a['private_id'], b['private_id']], original_conductor=current[1],
                        original_printed_names=[a['printed_name'], b['printed_name']],
                        resistance_ohm=str(value), native_milliohm=f[5], material_type_id=f[6], status=int(f[7])))+'\n')
                    # Independently reproduce the native .res.ext printer's
                    # float32 division and six-significant-digit formatting.
                    native_print = Decimal(format(f32(float(milliohm)/1000.), '.6g'))
                    printed[tuple(sorted([a['printed_name'], b['printed_name']])), native_print] += 1
                elif line.startswith('END '):
                    assert pending is None
                    current = None
    expected = Counter()
    for line in res.open():
        if line.startswith('resist '):
            f = shlex.split(line)
            expected[tuple(sorted(f[1:3])), Decimal(f[3])] += 1
    assert printed == expected and native_count == 166286
    save(out/'device_connections.json', device_rows)
    save(out/'nodes.json', nodes)
    paths = [Path(__file__).resolve(), owner, binding, original, retained, node_path, bind_path,
             original_path, retained_path, ext, provenance, res]
    save(out/'assessment.json', dict(input_sha256={str(p): sha(p) for p in paths},
        artifacts={str(p): sha(p) for p in out.iterdir()},
        private_native_voltage_nodes=len(nodes), wire_resistors=native_count,
        devices_bound_by_unique_physical_geometry=len(device_rows), minimum_wire_R_ohm=str(minimum),
        every_native_R_branch_multiplicity_and_value_recovered=True,
        original_conductor_device_connectivity_preserved_under_zero_wire_R=True,
        deliberately_wrong_gate_drain_binding_rejected=True,
        distinct_native_vertices_never_merged_by_printed_name_or_original_alias=True,
        legacy_reader_additive_R_bias_applied=False, original_device_cards_preserved_as_metadata=True,
        public_boundary_attachment_qualified=False, local_junction_distribution_qualified=False,
        distributed_capacitance_weights_or_transient_error_qualified=False,
        runtime_model_eligible=False, release_qualified=False, adopted=False))
    print('Private wire primitives:', native_count, 'positive R;', len(nodes), 'voltage nodes;', len(device_rows), 'devices bound by geometry. Runtime qualification remains open.')


if __name__ == '__main__':
    main()
