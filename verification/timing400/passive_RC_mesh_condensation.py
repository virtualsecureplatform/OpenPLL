"""Numerical DC harmonic elimination of general internal resistor meshes.

Retain every protected terminal. Construct only positive equivalent resistors;
capacitive energy must subsequently use full congruence, not voltage averaging.
Dynamic and oscillator error require separate validation.
"""
import numpy as np
from scipy.sparse import coo_matrix
from passive_RC_condensation import conductance


def harmonic_mesh(size, branches, eliminated, protected):
    removed = set(map(int, eliminated))
    if removed.intersection(protected):
        raise ValueError('Device/interface vertex cannot be eliminated')
    if not removed <= set(range(size)):
        raise ValueError('Unknown eliminated vertex')
    adjacency = [[] for _ in range(size)]
    for serial, (a, b, resistance) in enumerate(branches):
        assert a != b and 0 <= a < size and 0 <= b < size
        assert np.isfinite(float(resistance)) and float(resistance) > 0
        adjacency[a].append((b, serial)); adjacency[b].append((a, serial))
    kept = np.asarray([i for i in range(size) if i not in removed], dtype=np.int64)
    position = {int(i): j for j, i in enumerate(kept)}
    rr, cc, vv = list(map(int, kept)), list(range(len(kept))), [1.] * len(kept)
    G = conductance(size, branches)
    reduced, provenance, covered = [], [], set()
    for serial, (a, b, resistance) in enumerate(branches):
        if a not in removed and b not in removed:
            reduced.append((position[a], position[b], str(resistance)))
            covered.add(serial)
            provenance.append(dict(kind='unchanged', original_branch_indices=[serial]))
    pending = set(removed)
    while pending:
        first = min(pending); pending.remove(first)
        component, stack = {first}, [first]
        while stack:
            for neighbor, _ in adjacency[stack.pop()]:
                if neighbor in pending:
                    pending.remove(neighbor); component.add(neighbor); stack.append(neighbor)
        interior = sorted(component)
        anchors = sorted({neighbor for i in interior for neighbor, _ in adjacency[i] if neighbor not in removed})
        if not anchors:
            raise ValueError('Internal resistor component has no retained anchor')
        assert len(interior) <= 2048, 'Bound dense local solve size'
        serials = {serial for i in interior for _, serial in adjacency[i]}
        assert not serials.intersection(covered)
        covered.update(serials)
        Gii = G[interior][:, interior].toarray()
        positive_feed = -G[interior][:, anchors].toarray()
        weights = np.linalg.solve(Gii, positive_feed)
        assert np.isfinite(weights).all() and np.min(weights) >= 0
        assert max(abs(weights.sum(axis=1) - 1)) < 1e-10
        for i, original in enumerate(interior):
            for j, anchor in enumerate(anchors):
                if weights[i, j]:
                    rr.append(original); cc.append(position[anchor]); vv.append(float(weights[i, j]))
        # Off-diagonal Schur conductances are sums of nonnegative terms.
        # Avoid extracting them by subtracting nearly equal diagonal matrices.
        coupling = positive_feed.T @ weights
        scale = max(float(np.max(coupling)), 1e-300)
        assert np.max(abs(coupling - coupling.T)) < 1e-10 * scale
        for a in range(len(anchors)):
            for b in range(a + 1, len(anchors)):
                g = float((coupling[a, b] + coupling[b, a]) / 2)
                assert g >= 0
                if g:
                    reduced.append((position[anchors[a]], position[anchors[b]], format(1 / g, '.17g')))
        provenance.append(dict(kind='general_harmonic_component', removed_vertices=interior,
            original_endpoints=anchors, original_branch_indices=sorted(serials)))
    assert covered == set(range(len(branches)))
    T = coo_matrix((vv, (rr, cc)), shape=(size, len(kept))).tocsr()
    return T, kept, reduced, provenance
