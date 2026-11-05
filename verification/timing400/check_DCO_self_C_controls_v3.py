#!/usr/bin/env python3
"""Audit contact-normalized self operators and retain the failed metadata pass."""
import json
from pathlib import Path
import time

from check_local_C_operator_compilation import checked
from compile_local_C_operators_v2 import digest, save


def main():
    root = Path(__file__).resolve().parents[2]
    base = root/'build/timing400/release_001'
    owner = base/'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    paths = sorted((base/'local_C_self_pair_operator_controls_003').glob('*/assessment.json'))
    assert len(paths) == 12
    results, inputs = [], [Path(__file__).resolve(), owner, base/'DCO_self_C_extension_controls_001/assessment.json',
        base/'DCO_C_owner_trace_001/assessment.json']
    for path in paths:
        compiled = checked(path)
        identity_path = base/'local_C_self_increment_identity_controls_002'/path.parent.name/'assessment.json'
        identity = checked(identity_path)
        assert compiled['owner_contact_fields_normalized_using_exact_observed_native_plane_residues']
        assert identity['all_original_energy_operators_identical_under_exact_field_key_renaming']
        results.append(dict(case=path.parent.name, original_operators=identity['original_operators'],
            added_self_operators=identity['isolated_missing_self_operators'],
            contact_owner_fields_normalized=compiled['counts'].get('self_contact_field_normalizations', 0)))
        inputs.extend([path, identity_path])
    assert sum(r['contact_owner_fields_normalized'] for r in results) == 78
    example = base/'local_C_self_pair_operator_controls_003/nom_HD_narrow_FF/observed_plane_residues.json'
    residues = {(r['plane'], r['raw_type']): r['effective_type'] for r in json.loads(example.read_text())}
    assert residues[9, 48] == 91
    assert residues[8, 64] == 63 and residues[9, 64] == 91
    assert residues[9, 94] == 91 and residues[10, 94] == 98
    failure = base/'DCO_local_C_operators_nom_self_001/failure_and_supersession.json'
    assert not failure.exists()
    save(failure, dict(state='failed_complete_atlas_field_check',
        exception="AssertionError: ('sky130_fd_sc_hd__einvp_1_238.Z', 'locali', 'ndiffc')",
        cause='Owner side stream retained a contact type before the native surface helper applies DBPlaneToResidue.',
        correction='Use the exact deterministic plane/raw-type to effective-type mapping observed in the retained native SURFACE stream.',
        replacement='compile_local_C_operators_v5.py', native_retry_performed=False))
    inputs.extend([failure, example, Path(__file__).with_name('compile_local_C_operators_v4.py'),
        Path(__file__).with_name('check_DCO_self_C_controls_v2.py'),
        root/'build/timing400/magic_C_owner_source_001/extract/ExtBasic.c'])
    out = base/'DCO_self_C_extension_controls_002'
    out.mkdir(exist_ok=False)
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    save(out/'assessment.json', dict(all12_contact_normalized_self_operator_controls_passed=True,
        all_original_native_energy_operators_exactly_preserved=True,
        native_contact_plane_normalization_observations_checked=True,
        contact_type_has_distinct_active_and_locali_residues=True, results=results,
        prior_assessor_missing_observation_assumption_rejected='ND contact has no emitted active-plane sample in this control; actual poly and local-interconnect contacts exercise both planes.',
        original_operators=sum(r['original_operators'] for r in results),
        added_self_operators=sum(r['added_self_operators'] for r in results),
        corrected_full_DCO_passivity_qualified=False, runtime_model_eligible=False,
        release_qualified=False, adopted=False, deadline_uptime=deadline,
        input_sha256={str(p.resolve()): digest(p) for p in inputs}, artifacts={}))
    print('All twelve contact-normalized self-operator cases pass exact native-operator identity; no native result repeated.')


if __name__ == '__main__':
    main()
