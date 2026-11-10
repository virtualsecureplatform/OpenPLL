"""Independent endpoint coverage from successful native network output markers.

This is not a claim that every physical conductor is native-driver eligible.
Bulk-only, gate-only and C-only populations remain explicitly classified.
"""
import shlex
from collections import Counter
from audit_keeper_native_R_contraction import parse


def assess(reference, native_res_ext, original_ext):
    data = parse(reference)
    parent = {}

    def root(name):
        parent.setdefault(name, name)
        while parent[name] != name:
            parent[name] = parent[parent[name]]
            name = parent[name]
        return name

    # Native subcap markers use original EXT conductor owners; SPICE may
    # choose a different alias (notably the global substrate versus VGND).
    for line in original_ext.splitlines():
        if line.startswith('equiv '):
            fields = shlex.split(line)
            if len(fields) != 3:
                raise ValueError('literal source conductor equivalence required')
            parent[root(fields[1].lower())] = root(fields[2].lower())
    for a, b, value in data['resistors']:
        if value != 0:
            raise ValueError('coverage reference must contain only ideal port aliases')
        parent[root(a)] = root(b)
    ports = {root(n) for n in data['ports']}
    active, gates, bulk = set(), set(), set()
    for model, nodes, params in data['devices']:
        if 'nfet' in model or 'pfet' in model:
            if len(nodes) != 4:
                raise ValueError('four-terminal MOS required')
            active.update(root(nodes[i]) for i in (0, 2))
            gates.add(root(nodes[1]))
            bulk.add(root(nodes[3]))
        else:
            active.update(root(n) for n in nodes)
    required = active | ports
    gate_only = gates - required
    bulk_only = bulk - required - gates
    cap_nodes = {root(n) for a, b, value in data['caps'] for n in (a, b)}
    cap_only = cap_nodes - required - gates - bulk - {'0'}
    markers = Counter()
    for line in native_res_ext.splitlines():
        if line.startswith('subcap '):
            fields = shlex.split(line)
            if len(fields) != 3:
                raise ValueError('malformed native output marker')
            markers[root(fields[1].lower())] += 1
    duplicates = sorted(n for n, count in markers.items() if count > 1)
    missing = sorted(required - markers.keys())
    return dict(
        required_device_and_port_networks=len(required),
        successful_native_network_markers=sum(markers.values()),
        missing_required_networks=missing,
        duplicate_physical_network_markers=duplicates,
        device_and_port_output_coverage_verified=not missing and not duplicates,
        gate_only_networks=len(gate_only),
        gate_only_without_output=sorted(gate_only - markers.keys()),
        bulk_only_networks=len(bulk_only),
        bulk_only_without_output=sorted(bulk_only - markers.keys()),
        capacitance_only_networks=len(cap_only),
        capacitance_only_without_output_count=len(cap_only - markers.keys()),
        all_native_eligible_conductor_coverage_verified=False,
        scope='device source/drain/passive terminals and formal ports; other populations classified independently')
