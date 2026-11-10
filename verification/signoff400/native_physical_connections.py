"""Verify terminal ownership per physical device after wire contraction."""
from native_device_identity import inventory
from audit_keeper_native_R_contraction import parse


def assess(reference, candidate):
    before, after = inventory(reference), inventory(candidate)
    if before.keys() != after.keys():
        raise ValueError('physical device population changed')
    parent = {}

    def root(n):
        parent.setdefault(n, n)
        while parent[n] != n:
            parent[n] = parent[parent[n]]
            n = parent[n]
        return n

    baseline = parse(reference)
    for a, b, value in baseline['resistors']:
        if value != 0:
            raise ValueError('reference supports only ideal aliases')
        parent[root(a)] = root(b)
    known = {root(n) for row in before.values() for n in row['nodes']}
    known.update(root(n) for n in baseline['ports'])
    known.update(root(n) for a, b, v in baseline['caps'] for n in (a, b))
    # Freeze reference aliases before candidate unions.
    expected = {key: tuple(root(n) for n in row['nodes']) for key, row in before.items()}
    for a, b, value in parse(candidate)['resistors']:
        if value < 0:
            raise ValueError('negative wire resistance')
        parent[root(a)] = root(b)
    owners = {}
    for n in known:
        owners.setdefault(root(n), set()).add(n)
    collisions = [sorted(v) for v in owners.values() if len(v) > 1]

    def original(n):
        group = owners.get(root(n), set())
        return next(iter(group)) if len(group) == 1 else None

    failures = []
    for key, old_nodes in expected.items():
        row = after[key]
        nodes = tuple(original(n) for n in row['nodes'])
        options = [(nodes, row['parameters'])]
        model = key[0]
        if 'nfet' in model or 'pfet' in model:
            if len(nodes) != 4:
                raise ValueError('four-terminal MOS required')
            swapped = dict(row['parameters'])
            for a, b in [('ad', 'as'), ('pd', 'ps'), ('nrd', 'nrs')]:
                if (a in swapped) != (b in swapped):
                    raise ValueError('paired source/drain parameters required')
                if a in swapped:
                    swapped[a], swapped[b] = swapped[b], swapped[a]
            options.append(((nodes[2], nodes[1], nodes[0], nodes[3]), swapped))
        elif model == 'sky130_fd_pr__res_generic_po':
            options.append((tuple(reversed(nodes)), row['parameters']))
        if not any(n == old_nodes and p == before[key]['parameters'] for n, p in options):
            failures.append(dict(origin=key, reference_nodes=old_nodes,
                                 contracted_candidate_nodes=nodes))
    return dict(physical_devices_checked=len(before),
                per_physical_device_connections_verified=not failures and not collisions,
                conductor_collisions=collisions, failures=failures)
