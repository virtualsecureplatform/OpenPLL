#!/usr/bin/env python3
"""Numerically select fast nonterminal vertices by retaining slow anchors.

No degree restriction, model projection, state removal or native launch. The
internal RC comparison estimate is not an oscillator-frequency error bound.
"""
from collections import Counter
import json
import os
from pathlib import Path
import signal
import time
import numpy as np
from scipy.sparse import coo_matrix, load_npz
from scipy.sparse.csgraph import connected_components
from scipy.sparse.linalg import splu
from compile_local_C_operators_v2 import digest, save


def main():
    base = Path(__file__).resolve().parents[2] / 'build/timing400/release_001'
    owner = base / 'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    remaining = deadline - time.clock_gettime(time.CLOCK_BOOTTIME)
    assert remaining > 0
    signal.alarm(max(1, int(min(240, remaining))))
    original = base / 'DCO_all_internal_R_node_analysis_001'
    source = json.loads((original / 'assessment.json').read_text())
    assert source['candidate_nonterminal_states'] == 113934
    matrix = base / 'DCO_local_C_matrix_nom_no_substrate_G_001'
    nodes_path = matrix / 'nodes.json'
    names = json.loads(nodes_path.read_text())
    lookup = {name: index for index, name in enumerate(names)}
    rsource = base / 'DCO_domain_R_corners_002/nom_wire_R_unqualified.spice'
    rr, cc, vv = [], [], []
    for line in rsource.open():
        fields = line.split()
        if not fields or fields[0].startswith('*'): continue
        assert len(fields) == 4 and fields[0].startswith('R')
        a, b = lookup[fields[1]], lookup[fields[2]]
        g = 1 / float(fields[3])
        rr.extend([a, b, a, b]); cc.extend([a, b, b, a]); vv.extend([g, g, -g, -g])
    G = coo_matrix((vv, (rr, cc)), shape=(len(names), len(names))).tocsr()
    C = load_npz(matrix / 'C_native_units.npz').tocsr() * 1e-18
    selection = np.load(original / 'candidate_comparison_bounds.npz')['node_indices'].copy()
    out = base / 'DCO_adaptive_fast_internal_R_selection_nom_1fs_002'
    out.mkdir(exist_ok=False)
    target = 1e-15
    history, qualified = [], False
    for iteration in range(64):
        assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
        Gii = G[selection][:, selection].tocsc()
        mass = np.asarray(abs(C[selection][:, selection]).sum(axis=1)).ravel()
        bound = splu(Gii).solve(mass)
        residual = float(max(abs(Gii @ bound - mass)) / max(max(mass), 1e-300))
        assert np.isfinite(bound).all() and min(bound) >= -1e-10 * max(bound) and residual < 1e-8
        history.append(dict(iteration=iteration, selected_states=len(selection),
            maximum_comparison_time_s=float(max(bound)), relative_residual=residual))
        save(out / 'status.json', dict(state='analyzing_fast_nonterminal_selection',
            runner_pid=os.getpid(), deadline_uptime=deadline, current=history[-1]))
        save(out / 'iteration_history.json', history)
        if max(bound) <= target:
            qualified = True
            break
        # Retain the worst five percent of slow vertices in each component.
        # One vertex per component was insufficient for the large PG meshes.
        count, labels = connected_components(Gii, directed=False)
        ranked = np.lexsort((-bound, labels))
        boundaries = np.r_[0, np.flatnonzero(np.diff(labels[ranked])) + 1, len(ranked)]
        groups = []
        for start, end in zip(boundaries, boundaries[1:]):
            group = ranked[start:end]
            slow = int(np.count_nonzero(bound[group] > target))
            if slow:
                groups.append(group[:max(1, int(np.ceil(.05 * slow)))])
        remove = np.concatenate(groups)
        assert len(remove) > 0
        keep = np.ones(len(selection), dtype=bool); keep[remove] = False
        selection = selection[keep]
    # After an exhausted iteration cap the current bound belongs to the last
    # analyzed set, rather than its not-yet-analyzed proposed successor.
    if not qualified:
        save(out / 'assessment.json', dict(selection_converged=False,
            reason='bounded_iteration_cap_reached', iterations=history,
            active_model_changed=False, release_qualified=False, adopted=False))
        save(out / 'status.json', dict(state='iteration_cap_inconclusive', active_model_changed=False))
        return
    np.savez(out / 'selected_comparison_bounds.npz', node_indices=selection, upper_bounds_s=bound)
    inputs = [Path(__file__).resolve(), owner, original / 'assessment.json',
        original / 'candidate_comparison_bounds.npz', nodes_path, rsource, matrix / 'C_native_units.npz']
    save(out / 'assessment.json', dict(selection_converged=True,
        selected_nonterminal_states=len(selection), protected_device_and_point_vertices=34413,
        all_original_protected_vertices_retained=True, initial_nonterminal_candidates=113934,
        maximum_numerical_internal_comparison_bound_s=float(max(bound)),
        requested_comparison_limit_s=target, iterations=history,
        fraction_of_slow_vertices_retained_per_component_per_iteration=.05,
        independent_state_or_network_changed=False, model_projection_performed=False,
        numerical_selection_only=True, oscillator_frequency_error_qualified=False,
        runtime_model_eligible=False, release_qualified=False, adopted=False,
        deadline_uptime=deadline, input_sha256={str(p.resolve()): digest(p) for p in inputs},
        artifacts={str(p.resolve()): digest(p) for p in [out / 'selected_comparison_bounds.npz', out / 'iteration_history.json']}))
    save(out / 'status.json', dict(state='completed_numerical_selection', selected_states=len(selection)))
    print(json.dumps(dict(selected_nonterminal_states=len(selection), maximum_comparison_bound_s=float(max(bound)), iterations=len(history))))


if __name__ == '__main__':
    main()
