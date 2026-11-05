#!/usr/bin/env python3
"""Audit the self-pair extension and exact preservation of every native operator."""
import json
from pathlib import Path
import time
from compile_local_C_operators_v2 import digest, save
from check_local_C_operator_compilation import checked


def main():
    root = Path(__file__).resolve().parents[2]
    base = root/'build/timing400/release_001'
    owner = base/'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    controls = sorted((base/'local_C_self_pair_operator_controls_002').glob('*/assessment.json'))
    assert len(controls) == 12
    results, inputs = [], [Path(__file__).resolve(), owner]
    for path in controls:
        compiled = checked(path)
        identity_path = base/'local_C_self_increment_identity_controls_001'/path.parent.name/'assessment.json'
        identity = checked(identity_path)
        assert compiled['finite_R_same_conductor_pair_energy_restored']
        assert compiled['all_restored_pairs_have_zero_energy_under_ideal_conductor_collapse']
        assert identity['all_original_energy_operators_identical_under_exact_field_key_renaming']
        assert identity['isolated_missing_self_operators'] == compiled['counts'].get('restored_self_operators', 0)
        inputs.extend([path, identity_path])
        results.append(dict(case=path.parent.name, unchanged_original_operators=identity['original_operators'],
            added_self_operators=identity['isolated_missing_self_operators'],
            restored_self_pair_kernels=compiled['counts'].get('restored_self_pair_kernels', 0)))
    trace_path = base/'DCO_C_owner_trace_001/assessment.json'
    assert json.loads(trace_path.read_text())['nominal_native_C_devices_and_feedback_unchanged']
    inputs.append(trace_path)
    failure = base/'local_C_self_pair_operator_controls_001/failure_and_supersession.json'
    assert not failure.exists()
    save(failure, dict(state='reader_failed_before_completing_first_case',
        exception='KeyError: FRINGE_SHIELD_GEOMETRY',
        cause='Copying defaultdict into dict removed empty-list behavior for a kernel with no shield records.',
        replacement='compile_local_C_operators_v4.py', native_retry_performed=False))
    inputs.extend([failure, Path(__file__).with_name('compile_local_C_operators_v3.py')])
    out = base/'DCO_self_C_extension_controls_001'
    out.mkdir(exist_ok=False)
    result = dict(all12_self_pair_operator_extension_controls_passed=True,
        all_original_native_energy_operators_exactly_preserved=True,
        native_nonzero_G_P_event_and_ground_conventions_preserved=True,
        self_terms_have_zero_energy_under_logical_conductor_collapse=True,
        results=results, original_operators=sum(r['unchanged_original_operators'] for r in results),
        added_self_operators=sum(r['added_self_operators'] for r in results),
        full_corrected_DCO_matrix_passivity_qualified=False,
        runtime_model_eligible=False, release_qualified=False, adopted=False, deadline_uptime=deadline,
        input_sha256={str(p.resolve()): digest(p) for p in inputs}, artifacts={})
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    save(out/'assessment.json', result)
    print(json.dumps({k:v for k,v in result.items() if k not in ['input_sha256','artifacts','results']}, indent=2))


if __name__ == '__main__':
    main()
