#!/usr/bin/env python3
"""Build exact piecewise-linear voltage bases on retained native wire tiles.

This supplies an integrator for future local charge kernels. Do not interpret
coarse native C support boxes as uniform charge distributions.
"""
from collections import Counter, defaultdict
from fractions import Fraction
import json
import math
from pathlib import Path
import signal
import time
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT, sha, save


def voltage_weights_at(x, knots):
    x = Fraction(x)
    if x <= knots[0][0]:
        return {knots[0][1]: Fraction(1)}
    if x >= knots[-1][0]:
        return {knots[-1][1]: Fraction(1)}
    for (a, na), (b, nb) in zip(knots, knots[1:]):
        if a <= x <= b:
            f = (x-a)/(b-a)
            result = defaultdict(Fraction)
            result[na] += 1-f
            result[nb] += f
            return {k: v for k, v in result.items() if v}
    raise AssertionError((x, knots))


def integrated_voltage_weights(lo, hi, knots):
    assert lo < hi
    cuts = [Fraction(lo), *[Fraction(x) for x, _ in knots if lo < x < hi], Fraction(hi)]
    result = defaultdict(Fraction)
    for a, b in zip(cuts, cuts[1:]):
        for node, value in voltage_weights_at((a+b)/2, knots).items():
            result[node] += value*(b-a)
    assert all(v >= 0 for v in result.values())
    assert sum(result.values()) == hi-lo
    return dict(result)


def analytic_controls():
    knots = [(2, 'a'), (5, 'b'), (11, 'c')]
    coords = dict(a=2, b=5, c=11)
    whole = integrated_voltage_weights(0, 12, knots)
    interior = integrated_voltage_weights(3, 9, knots)
    assert sum(whole[k]*coords[k] for k in whole) == Fraction(147, 2)
    assert sum(interior[k]*coords[k] for k in interior) == 36
    assert voltage_weights_at(4, knots) == {'a': Fraction(1, 3), 'b': Fraction(2, 3)}
    assert voltage_weights_at(1, knots) == {'a': Fraction(1)}
    assert voltage_weights_at(13, knots) == {'c': Fraction(1)}
    wrong = integrated_voltage_weights(3, 9, [(2, 'c'), (5, 'b'), (11, 'a')])
    assert sum(wrong[k]*coords[k] for k in wrong) != 36
    return dict(nonuniform_chain_affine_patch_passed=True, outside_chain_clamp_integral_passed=True,
        reversed_endpoint_orientation_control_rejected=True, exact_rational_partition_of_unity_passed=True)


def main():
    controls = analytic_controls()
    base = ROOT/'build/timing400/release_001'
    owner = base/'distributed_RC_model_qualification_001/owner.json'
    left = json.loads(owner.read_text())['deadline_uptime']-time.clock_gettime(time.CLOCK_BOOTTIME)
    assert left > 0
    signal.alarm(max(1, math.floor(left)))
    proof = base/'DCO_private_wire_creation_geometry_002/assessment.json'
    assert verify(proof)['all_wire_creation_endpoint_orientations_unique']
    source = proof.parent/'wire_geometry.jsonl'
    groups = defaultdict(list)
    counts = Counter()
    for line in source.open():
        row = json.loads(line)
        axis = 0 if row['status'] & 0x200 else 1
        key = row['original_conductor'], row['material_type_id'], tuple(row['creation_tile_internal']), axis
        a, b = [p[axis] for p in row['creation_breakpoints_internal']]
        assert a < b
        na, nb = row['oriented_private_nodes']
        groups[key].append((a, b, na, nb, row['index']))
        if not key[2][axis] <= a < b <= key[2][axis+2]:
            counts['branch_breakpoints_extend_outside_creation_tile'] += 1
    out = base/'DCO_native_tile_voltage_basis_001'
    out.mkdir(exist_ok=False)
    with (out/'tile_voltage_bases.jsonl').open('x') as stream:
        for key, segments in groups.items():
            segments.sort(key=lambda s: s[:2])
            for before, after in zip(segments, segments[1:]):
                assert before[1] == after[0], ('chain gap/overlap', key, before, after)
                assert before[3] == after[2], ('chain discontinuity', key, before, after)
            knots = [(segments[0][0], segments[0][2]), *[(s[1], s[3]) for s in segments]]
            box, axis = key[2:]
            lo, hi = box[axis], box[axis+2]
            weights = integrated_voltage_weights(lo, hi, knots)
            normalized = {node: value/(hi-lo) for node, value in weights.items() if value}
            assert sum(normalized.values()) == 1 and all(v >= 0 for v in normalized.values())
            counts['tiles'] += 1
            counts['wire_branches'] += len(segments)
            counts['tiles_with_axis_open_end_extension'] += lo < knots[0][0] or hi > knots[-1][0]
            counts['tiles_with_repeated_voltage_node_at_multiple_axis_positions'] += len({n for _, n in knots}) < len(knots)
            stream.write(json.dumps(dict(index=counts['tiles'], original_conductor=key[0], material_type_id=key[1],
                creation_tile_internal=list(box), axis=axis, voltage_knots_internal=knots,
                wire_branch_indices=[s[4] for s in segments],
                uniform_axis_average_weights={node: str(value) for node, value in normalized.items()},
                uniform_axis_density_is_not_assumed_for_C_contributions=True))+'\n')
    assert counts['tiles'] == 55663 and counts['wire_branches'] == 130708
    save(out/'analytic_controls.json', controls)
    inputs = [Path(__file__).resolve(), owner, proof, source]
    artifacts = [out/'tile_voltage_bases.jsonl', out/'analytic_controls.json']
    save(out/'assessment.json', dict(input_sha256={str(p): sha(p) for p in inputs},
        artifacts={str(p): sha(p) for p in artifacts}, counts=dict(counts), analytic_controls=controls,
        native_tile_chains_continuous_with_no_axis_gaps_or_overlaps=True,
        exact_nonnegative_partition_of_unity_for_all_uniform_axis_integrals=True,
        C_local_charge_kernels_preserved=False, C_contribution_weights_emitted=False,
        transverse_voltage_open_end_R_and_spatial_integration_error_qualified=False,
        runtime_model_eligible=False, release_qualified=False, adopted=False))
    print('Exact native tile voltage bases:', dict(counts), '; analytic controls passed; C kernels still required.')


if __name__ == '__main__':
    main()
