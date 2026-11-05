#!/usr/bin/env python3
"""Prepare, without launching, the corrected-C full-R exact-ground diagnostic."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import time
from compile_local_C_operators_v2 import digest, save


def noncapacitive_identity(path, deadline):
    checksum = hashlib.sha256()
    counts = Counter()
    for number, line in enumerate(path.open()):
        if number % 100000 == 0:
            assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
        words = line.split()
        if not words or words[0].startswith('*'):
            continue
        if words[0].upper().startswith('CFIELD_'):
            counts['C'] += 1
            continue
        checksum.update((' '.join(words) + '\n').encode())
        if words[0][0].upper() in 'RMV':
            counts[words[0][0].upper()] += 1
    return checksum.hexdigest(), dict(counts)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    base = root / 'build/timing400/release_001'
    owner = base / 'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    old = base / 'DCO_domain_candidate_nom_001/candidate_unqualified.spice'
    corrected = base / 'DCO_domain_candidate_nom_substrate_output_001'
    new = corrected / 'candidate_unqualified.spice'
    proof_path = corrected / 'assessment.json'
    proof = json.loads(proof_path.read_text())
    assert proof['source_matrix_numerical_passivity_check_passed']
    assert proof['signed_matrix_branch_realization_readback_passed']
    assert proof['native_substrate_output_G_convention_experiment']
    assert proof['source_original_substrate_G_operators_omitted'] == 1113704
    assert not proof['release_qualified'] and not proof['adopted']
    prior = base / 'DCO_domain_nom_tt27_c0_f247_80ns_canonical_ground_001'
    manifest_path = prior / 'input_manifest.json'
    manifest = json.loads(manifest_path.read_text())
    pins = manifest['input_sha256'].copy()
    pins.update(proof['input_sha256'])
    pins.update(proof['artifacts'])
    for name, value in pins.items():
        assert digest(Path(name)) == value, name
    prior_hash, old_counts = noncapacitive_identity(old, deadline)
    corrected_hash, new_counts = noncapacitive_identity(new, deadline)
    assert prior_hash == corrected_hash
    assert old_counts['C'] == 5508102 and new_counts['C'] == 5492690
    assert {k: v for k, v in old_counts.items() if k != 'C'} == {
        k: v for k, v in new_counts.items() if k != 'C'}
    original = (prior / 'point.cir').read_text()
    previous_include = f'.include "{old.resolve()}"'
    replacement_include = f'.include "{new.resolve()}"'
    assert original.count(previous_include) == 1
    prepared = original.replace(previous_include, replacement_include)
    assert prepared.replace(replacement_include, previous_include) == original
    assert '.tran 20p 80n 0 10p UIC' in prepared
    assert '.print TRAN FORMAT=STD PRECISION=16 V(PLLOUT) I(VVPWR)' in prepared
    # Constant capacitors are open at DC: unchanged R/M/V topology means the
    # already checked saved bias applies without recalculating or rounding it.
    initial = prior / 'initial_bias_canonical_ground.ic'
    assert f'.include "{initial.resolve()}"' in prepared
    audit_path = base / 'DCO_ground_coordinate_mapping_checks_001/assessment.json'
    audit = json.loads(audit_path.read_text())
    assert audit['independent_full_boundary_and_initial_charge_mapping_passed']
    for path in [Path(__file__).resolve(), owner, manifest_path, proof_path,
                 prior / 'point.cir', initial, audit_path]:
        pins[str(path.resolve())] = digest(path)
    args.output.mkdir(exist_ok=False)
    deck = args.output / 'point.cir'
    deck.write_text(prepared)
    pins[str(deck.resolve())] = digest(deck)
    save(args.output / 'input_manifest.json', dict(input_sha256=pins,
        parameters=manifest['parameters'], original_deadline_uptime=deadline,
        physical_C_model_changed=True, sole_testbench_change='physical macro include path',
        saved_initial_bias_unchanged=True, budget_restarted=False,
        native_started=False, automatic_launch=False))
    save(args.output / 'assessment.json', dict(
        corrected_C_diagnostic_preparation_passed=True,
        all_noncapacitive_macro_statements_identical=True,
        noncapacitive_statements_sha256=corrected_hash,
        prior_macro_component_counts=old_counts, corrected_macro_component_counts=new_counts,
        full_finite_R_and_device_model_preserved=True,
        exact_ground_boundary_and_saved_DC_bias_reused=True,
        source_substrate_output_convention_changed=True,
        original_deadline_uptime=deadline, budget_restarted=False,
        native_started=False, automatic_launch=False,
        physical_dynamic_or_frequency_error_qualified=False,
        runtime_model_eligible=False, release_qualified=False, adopted=False,
        input_sha256=pins))
    print('PASS: corrected-C full-R deck prepared; all non-C statements identical; no native instance launched.')


if __name__ == '__main__':
    main()
