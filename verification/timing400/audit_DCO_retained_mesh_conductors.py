#!/usr/bin/env python3
"""Check retained-mesh connectivity against original MOS and public terminals.

Collapse wire R only for this conductor-identity proof. Keep every voltage node
in the extracted model. A connected mesh component must bind to exactly one
original conductor, and every R/MOS/port node must have a terminal binding.
This does not establish R magnitudes, impedance equivalence or C placement.
"""
from collections import defaultdict
import json
import math
from pathlib import Path
import signal
import time
from audit_active_dco_rc_capacitance import parse, terminals
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT, sha, save


def main():
    base = ROOT/'build/timing400/release_001'
    owner = base/'distributed_RC_model_qualification_001/owner.json'
    left = json.loads(owner.read_text())['deadline_uptime']-time.clock_gettime(time.CLOCK_BOOTTIME)
    assert left > 0
    signal.alarm(max(1, math.floor(left)))
    proof = base/'DCO_retained_R_mesh_001/assessment.json'
    assert verify(proof)['public_ports_preserved']
    original = base/'active_dco_lumped_capacitance_export_001/lumped_full.spice'
    top = 'IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160'
    path = proof.parent/'trace'/(top+'.rcx.spice')
    before, after = parse(original), parse(path)
    parent = {}
    def find(node):
        parent.setdefault(node, node)
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node
    for a, b, value in after['R']:
        assert value > 0
        parent[find(a)] = find(b)
    labels = defaultdict(set)
    active = {n for a, b, value in after['R'] for n in [a, b]} | set(after['ports'])
    assert before['ports'] == after['ports'] and before['X'].keys() == after['X'].keys()
    for port in before['ports']:
        labels[find(port)].add(port)
    terminal_count = 0
    for name, row in before['X'].items():
        other = after['X'][name]
        n = terminals(row)
        assert n == terminals(other) and row[n] == other[n]
        for original_node, mesh_node in zip(row[:n], other[:n]):
            active.add(mesh_node)
            labels[find(mesh_node)].add(original_node)
            terminal_count += 1
    ambiguous = {root: sorted(names) for root, names in labels.items() if len(names) != 1}
    unbound = [node for node in active if not labels[find(node)]]
    assert not ambiguous and not unbound, (list(ambiguous.items())[:4], unbound[:4])
    canonical = {node: next(iter(labels[find(node)])) for node in active}
    out = base/'DCO_retained_R_mesh_conductor_audit_001'
    out.mkdir(exist_ok=False)
    save(out/'node_conductors.json', canonical)
    paths = [Path(__file__).resolve(), owner, proof, original, path,
             Path(__file__).with_name('audit_active_dco_rc_capacitance.py')]
    save(out/'assessment.json', dict(input_sha256={str(p): sha(p) for p in paths},
        artifacts={str(out/'node_conductors.json'): sha(out/'node_conductors.json')},
        retained_R_MOS_and_port_nodes=len(active), original_conductors=len(set(canonical.values())),
        device_terminals_checked=terminal_count, ambiguous_or_missing_conductor_bindings=0,
        all_original_MOS_resistor_and_public_terminal_conductor_identities_preserved=True,
        voltage_nodes_merged_in_runtime_model=False, R_electrical_equivalence_qualified=False,
        physical_C_placement_or_transient_error_qualified=False, release_qualified=False, adopted=False))
    print('Retained mesh conductor identities:', len(active), 'nodes;', terminal_count, 'device terminals; no shorts or missing bindings.')


if __name__ == '__main__':
    main()
