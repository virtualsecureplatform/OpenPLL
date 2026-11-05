#!/usr/bin/env python3
"""Independent integral and domain-ownership controls for the C assembler."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import time

from assemble_local_C_matrix import Atlas, integrate_operator
from compile_local_C_operators_v2 import digest, save
from local_C_field_integrals import controls


def main():
    root = Path(__file__).resolve().parents[2]
    base = root/'build/timing400/release_001'
    owner = base/'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    result = controls()
    fields = [['@SUBSTRATE_REFERENCE', 'reference', 'reference'], ['a', 'metal1', 'metal1']]
    with TemporaryDirectory() as name:
        domain_path = Path(name)/'domains.jsonl'
        # Adjacent domains have different independent voltage fields. Both
        # rectangle and edge integration must partition at their shared seam.
        rows = [dict(original_conductor='a', plane='metal1', effective_material='metal1',
            box_internal=[lo, 0, hi, 3], axis=0,
            voltage_knots_internal=[[lo, f'n{i}'], [hi, f'n{i+1}']])
            for i, (lo, hi) in enumerate([(0, 2), (2, 6)])]
        domain_path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
        atlas = Atlas(domain_path, fields)
        operators = [
            ['A', 1, 0, 1, [0, 0, 6, 3], 1.],
            ['L', 1, 0, 2, [0, 0, 6, 0], [0, 0, 6, 0], 1., 8, 0]]
        for row, expected in zip(operators, [18., 6.]):
            matrices = list(integrate_operator(atlas, row))
            assert len(matrices) == 2
            # Uniform voltage on the entire logical conductor recovers the
            # native scalar, despite its several distinct private vertices.
            energy = sum(value for matrix in matrices for (a, b), value in matrix.items()
                         if a != '_dco_substrate_reference' and b != '_dco_substrate_reference'
                         for _ in range(1 if a == b else 2))
            assert abs(energy-expected) < 1e-13
        rejected = 0
        for row in [
            ['L', 1, 0, 3, [0, 0, 6, 0], [0, 0, 6, 0], 1., 2, 0],
            ['A', 1, 0, 4, [0, 0, 7, 3], 1.]]:
            try:
                list(integrate_operator(atlas, row))
            except AssertionError:
                rejected += 1
        assert rejected == 2
    result.update(adjacent_independent_domain_area_and_edge_partition_controls=2,
        wrong_inward_side_and_uncovered_area_negative_controls_rejected=2)
    out = base/'local_C_field_integral_controls_001'
    out.mkdir(exist_ok=False)
    files = [Path(__file__).resolve(), owner, *[Path(__file__).with_name(n) for n in
        ['assemble_local_C_matrix.py', 'local_C_field_integrals.py',
         'local_C_energy_integration.py', 'compile_local_C_operators_v2.py']]]
    receipt = dict(controls=result, local_field_integral_controls_passed=True,
        deadline_uptime=deadline, input_sha256={str(p.resolve()): digest(p) for p in files},
        artifacts={}, signed_global_DCO_passivity_qualified=False,
        runtime_model_eligible=False, release_qualified=False, adopted=False)
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    save(out/'assessment.json', receipt)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
