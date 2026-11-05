#!/usr/bin/env python3
"""Record the measured matrix rejection and controlled self-coupling followup."""
from datetime import datetime, timezone
import json
from pathlib import Path
import time
import numpy as np
from scipy.sparse import load_npz

from compile_local_C_operators_v2 import digest, save
from record_qualification_progress_045 import process


def main():
    root = Path(__file__).resolve().parents[2]
    base = root/'build/timing400/release_001'
    owner = base/'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    receipt_names = ['DCO_corner_C_operators_001', 'DCO_domain_R_corners_002',
        'DCO_contact_cut_count_geometry_001', 'DCO_poly_resistor_charge_accounting_001',
        'signed_C_Xyce_controls_002', 'DCO_local_C_matrix_nom_001', 'DCO_local_C_matrix_nom_checks_001',
        'DCO_negative_C_diagonal_diagnosis_001', 'DCO_negative_C_kernel_inspection_002',
        'DCO_corner_matrix_stop_after_nominal_failure_001', 'magic_C_owner_source_preparation_001',
        'magic_C_owner_trace_patch_001', 'magic_C_owner_trace_build_001', 'magic_C_owner_controls_001']
    receipts = [base/n/'assessment.json' for n in receipt_names]
    rows = [json.loads(p.read_text()) for p in receipts]
    corners, rvalues, cuts, poly, signed, matrix, check, diagnosis, inspection, stopped, prep, patch, build, controls = rows
    assert corners['all_three_RC_corner_operator_integrals_and_ownership_passed']
    assert rvalues['all166286_nominal_values_reproduce_native_float32_formulas_exactly']
    assert cuts['all35578_native_contact_branch_cut_counts_match_actual_GDS']
    assert poly['generic_poly_resistor_native_and_PDK_charge_accounting_complete']
    assert signed['golden_Xyce_signed_capacitor_mass_matrix_controls_passed']
    assert matrix['full_nominal_C_energy_matrix_assembled']
    assert check['zero_wire_R_collapse_matches_owned_physical_operator_totals']
    assert not check['signed_global_passivity_numerical_check_passed']
    assert controls['all12_owner_trace_native_equivalence_and_accounting_controls_passed']
    assert inspection['explicit_same_ideal_conductor_skipped_pair_kernels'] == 6
    m = load_npz(base/'DCO_local_C_matrix_nom_001/C_native_units.npz')
    norm = np.asarray(abs(m).sum(axis=1)).ravel()
    negatives = np.flatnonzero(m.diagonal() < -1e-12*np.maximum(norm, 1e-30))
    assert len(negatives) == 101
    notes = [
        ('DCO_domain_R_corners_001', dict(state='failed_before_emitting_decks',
            exception='TypeError: JSON cannot serialize tuple dictionary keys',
            replacement='DCO_domain_R_corners_002', native_runs_added=0)),
        ('signed_C_Xyce_controls_001', dict(state='baseline_native_passed_reader_failed',
            initial_environment_failure='pya Python lacks NumPy; no native process started in that attempt',
            reader_exception='KeyError: V(a); native CSV uses V(A)',
            replacement='signed_C_Xyce_controls_002', baseline_native_result_reused=True, identical_native_retry=False)),
        ('DCO_negative_C_kernel_inspection_001', dict(state='reader_failed_on_overly_narrow_kind_assertion',
            exception='Assertion assumed all negative terms were FRINGE_HALO; two selected terms are BLOCKED_FRINGE',
            replacement='DCO_negative_C_kernel_inspection_002', native_runs_added=0))]
    note_paths = []
    for folder, note in notes:
        path = base/folder/'failure_and_supersession.json'
        assert not path.exists()
        save(path, note)
        note_paths.append(path)
    jobs = []
    for p in Path('/proc').glob('[0-9]*'):
        try:
            name = (p/'comm').read_text().strip()
            if name in ['Xyce', 'ngspice', 'magicdnull']:
                row = process(int(p.name))
                if row['live']:
                    jobs.append(dict(kind=name, **row))
        except (FileNotFoundError, ProcessLookupError):
            continue
    assert len(jobs) <= 4
    trace_dir = base/'DCO_C_owner_trace_001'
    trace_status = json.loads((trace_dir/'status.json').read_text())
    trace_owner = json.loads((trace_dir/'owner.json').read_text())
    runner = process(trace_owner['runner_pid'])
    trace_receipt = trace_dir/'assessment.json'
    trace_passed = False
    if trace_receipt.exists():
        trace_passed = json.loads(trace_receipt.read_text())['nominal_native_C_devices_and_feedback_unchanged']
        receipts.append(trace_receipt)
    for name, expected in {
        'verification/release_requirements_400mhz.json': '02911569a2538d8b4d6c3139decdf7ec4d7c33bf2cbad85eed442947c0022b52',
        'verification/release_plan_400mhz.json': '2d6d5ed4404df842d64d42d68ebe593e4f627e65b4f90aaa48bef5f991e94b02'}.items():
        assert digest(root/name) == expected
    previous = base/'qualification_progress_060.json'
    progress = json.loads(previous.read_text())
    evidence = dict(receipts={p.parent.name: str(p.relative_to(root)) for p in receipts},
        all_three_RC_operator_streams_compiled_and_checked=True,
        all166286_fixed_mesh_R_corner_values_recomputed_and_read_back=True,
        all35578_contact_branches_match_actual_GDS_cut_counts=True,
        generic_poly_PDK_and_native_charge_accounting_complete=True,
        golden_Xyce_signed_branch_realization_control_passed=True,
        actual_time_step_refinement_exercised_by_signed_branch_control=False,
        signed_branch_control_scope='Both configured max-step variants use identical adaptive samples; compatibility only, not DCO convergence.',
        nominal_full_C_matrix_assembled=True, matrix_vertices=m.shape[0], matrix_nonzeros=m.nnz,
        native_zero_R_capacitance_collapse_passed=True,
        rejected_matrix='build/timing400/release_001/DCO_local_C_matrix_nom_001',
        negative_diagonal_entries=len(negatives), minimum_normalized_eigenvalue=min(check['normalized_minimum_eigenvalues']),
        nominal_matrix_passivity_failed=True, nominal_matrix_runtime_adoption_forbidden=True,
        worst_diagonal_native_units=diagnosis['negative_diagonal_native_cap_units'],
        six_of_ten_largest_negative_terms_explicitly_skip_same_ideal_conductor_pairs=True,
        candidate_repair='Capture and restore geometrically owned same-conductor overlap/fringe/sidewall coupling; recheck full passivity.',
        repair_sufficiency_proven=False, two_corner_assemblers_stopped_after_nominal_failure=True,
        owner_tracer_build_and_all12_equivalence_controls_passed=True,
        actual_DCO_owner_trace_status_at_observation=trace_status,
        actual_DCO_owner_trace_native_equivalence_passed=trace_passed,
        actual_DCO_owner_trace_runner=runner,
        original_deadline_uptime=deadline, budget_restarted=False,
        runtime_model_eligible=False, release_qualified=False, adopted=False)
    inputs = [Path(__file__).resolve(), previous, owner, *receipts, *note_paths,
        root/'verification/release_requirements_400mhz.json', root/'verification/release_plan_400mhz.json',
        Path(__file__).with_name('build_DCO_domain_R_corners.py'),
        Path(__file__).with_name('check_signed_C_Xyce.py'),
        Path(__file__).with_name('inspect_DCO_negative_C_kernels.py')]
    progress.update(observed_utc=datetime.now(timezone.utc).isoformat(),
        classification='full_nominal_C_matrix_rejected_by_passivity_R_corners_GDS_cuts_and_poly_charge_passed_controlled_self_coupling_trace_underway',
        evidence_sha256={str(p.relative_to(root)): digest(p) for p in inputs},
        distributed_C_passivity_failure_and_self_coupling_followup=evidence,
        active_distributed_RC_followups=[runner] if runner['live'] else [],
        native_analog_jobs=jobs, native_analog_count=sum(r['kind'] in ['Xyce', 'ngspice'] for r in jobs),
        current_native_CAD_and_analog_engines=jobs,
        release_qualified=False, adopted=False, physical_whole_pll_passes=0)
    progress['next_actions'] = [
        'Finish actual-DCO owner tracing, preserving native C/devices/feedback; compile omitted finite-R self-coupling operators',
        'Assemble the corrected nominal matrix and require zero-R conservation plus global passivity before any candidate transient',
        'Complete corrected min/max models, numerical and integration qualification, then frozen15PVT four-mode calibration/timing/wholePLL release gates']
    snapshot = base/'qualification_progress_061.json'
    assert not snapshot.exists()
    save(snapshot, progress)
    overview = root/'build/timing450/implementation_assessment.json'
    state = json.loads(overview.read_text())
    state['latest_400mhz_qualification_progress'] = str(snapshot.relative_to(root))
    state['active_400mhz_distributed_C_passivity_failure_and_self_coupling_followup'] = evidence
    state['active_400mhz_distributed_RC_followups'] = progress['active_distributed_RC_followups']
    state['rejected_400mhz_distributed_C_matrix'] = dict(directory=evidence['rejected_matrix'],
        reason='101 negative diagonal entries; normalized minimum eigenvalue -0.3333764', runtime_adoption_forbidden=True)
    state['active_400mhz_distributed_RC_check'] = dict(owner=str(owner.relative_to(root)),
        state='nominal_C_passivity_failed_controlled_self_coupling_repair_in_progress', deadline_uptime=deadline,
        native_analog_jobs=progress['native_analog_count'], native_CAD_jobs=sum(r['kind'] == 'magicdnull' for r in jobs),
        release_qualified=False)
    for key in ['release_qualified', 'selected', 'timing_closure_complete']:
        state[key] = False
    save(overview, state)
    print('Progress061: nonpassive nominal matrix rejected; R/cut/poly/compatibility controls passed; controlled same-conductor repair underway.')


if __name__ == '__main__':
    main()
