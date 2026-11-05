#!/usr/bin/env python3
"""Reconcile native R records with SPICE export, retaining pointer identities.

Original pre-R equivalences explain exporter names, but they are not permission
to merge distinct voltage nodes in a distributed RC model. Classify every
removed branch using its actual native pointers, independently of printed names.
"""
from collections import Counter, defaultdict
from decimal import Decimal
import json
import math
from pathlib import Path
import shlex
import signal
import time
from check_compact_clock_tree import verify
from inspect_DCO_retained_R_mesh_geometry import provenance
from run_dco_qualification import ROOT, sha, save


def half_print_interval(value):
    return Decimal(10)**(value.copy_abs().adjusted()-5)/2 if value else Decimal(0)


def main():
    base = ROOT/'build/timing400/release_001'
    owner = base/'distributed_RC_model_qualification_001/owner.json'
    left = json.loads(owner.read_text())['deadline_uptime']-time.clock_gettime(time.CLOCK_BOOTTIME)
    assert left > 0
    signal.alarm(max(1, math.floor(left)))
    proof = base/'DCO_retained_R_mesh_001/assessment.json'
    assert verify(proof)['original_pre_RC_C_matrix_and_devices_preserved']
    source = proof.parent/'trace'
    top = 'IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160'
    ext, res, spice = [source/(top+suffix) for suffix in ['.ext', '.res.ext', '.rcx.spice']]
    parent = {}
    def find(n):
        parent.setdefault(n, n)
        while parent[n] != n:
            parent[n] = parent[parent[n]]
            n = parent[n]
        return n
    equivalences = 0
    for line in ext.open():
        if line.startswith('equiv '):
            f = shlex.split(line)
            parent[find(f[1])] = find(f[2])
            equivalences += 1
    native, exported = defaultdict(list), defaultdict(list)
    loops, literal_loops = Counter(), 0
    for line in res.open():
        if not line.startswith('resist '):
            continue
        f = shlex.split(line)
        a, b = sorted([find(f[1]), find(f[2])])
        value = Decimal(f[3])  # .res.ext resist values are ohms.
        if a == b:
            loops[tuple(sorted(f[1:3]))] += 1
            literal_loops += f[1] == f[2]
        else:
            native[a, b].append(value)
    for line in spice.open():
        if line.startswith('R'):
            f = line.split()
            exported[tuple(sorted([find(f[1]), find(f[2])]))].append(Decimal(f[3]))
    assert native.keys() == exported.keys()
    changed = []
    for key, values in native.items():
        other = exported[key]
        assert len(values) == len(other), key
        for a, b in zip(sorted(values), sorted(other)):
            allowance = half_print_interval(a)+half_print_interval(b)
            if abs(a-b) > allowance:
                changed.append(dict(nodes=list(key), native_ohm=str(a), SPICE_ohm=str(b), allowance_ohm=str(allowance)))
    assert not changed, changed[:4]
    types, groups = provenance(source/'R_provenance.log')
    last = {g['original']: g for g in groups.values()}
    omitted, classification, pointer_loop_pairs = [], Counter(), Counter()
    for group in last.values():
        offsets, seen = Counter(), set()
        for owner_ptr, a, b, value, type_id, status in group['edges']:
            ptr = group['branches'][owner_ptr][offsets[owner_ptr]]
            offsets[owner_ptr] += 1
            if ptr in seen:
                continue
            seen.add(ptr)
            na, nb = [group['nodes'][p] for p in [a, b]]
            if find(na['name']) != find(nb['name']):
                continue
            key = tuple(sorted([na['name'], nb['name']]))
            pointer_loop_pairs[key] += 1
            state = ('same_native_pointer' if a == b else
                     'distinct_pointers_same_printed_name' if na['name'] == nb['name'] else
                     'distinct_pointers_original_equivalence_aliases')
            classification[state] += 1
            omitted.append(dict(original_conductor=group['original'], classification=state,
                native_group=group['id'], native_branch=ptr, native_nodes=[a, b],
                names=[na['name'], nb['name']], points_internal=[na['point'], nb['point']],
                milliohm=value, material=types[type_id], status=int(status)))
    assert pointer_loop_pairs == loops
    out = base/'DCO_R_export_alias_audit_001'
    out.mkdir(exist_ok=False)
    save(out/'omitted_branches.json', omitted)
    paths = [Path(__file__).resolve(), owner, proof, ext, res, spice, source/'R_provenance.log',
             Path(__file__).with_name('inspect_DCO_retained_R_mesh_geometry.py')]
    save(out/'assessment.json', dict(input_sha256={str(p): sha(p) for p in paths},
        artifacts={str(out/'omitted_branches.json'): sha(out/'omitted_branches.json')},
        original_equivalence_records=equivalences, native_resistor_records=sum(map(len, native.values()))+sum(loops.values()),
        exported_resistors=sum(map(len, exported.values())), omitted_alias_self_loop_resistors=sum(loops.values()),
        literal_same_name_resistors=literal_loops, omitted_branch_classification=dict(classification),
        remaining_branch_multiplicity_and_values_preserved_within_print_intervals=True,
        all_exported_and_omitted_branches_reconciled=True,
        original_aliases_are_not_a_distributed_voltage_node_equivalence_proof=True,
        distinct_native_voltage_node_alias_collapse_qualified=False,
        RC_model_electrical_equivalence_or_spatial_C_qualified=False, release_qualified=False, adopted=False))
    print('Native-to-SPICE R export reconciled:', dict(classification), '; remaining branches preserve multiplicity and values.')


if __name__ == '__main__':
    main()
