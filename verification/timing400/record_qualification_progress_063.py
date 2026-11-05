#!/usr/bin/env python3
"""Record complete restored C checks, remaining max-C failure and native work."""
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from compile_local_C_operators_v2 import digest, save
from record_qualification_progress_045 import process


def main():
    root = Path(__file__).resolve().parents[2]
    base = root/'build/timing400/release_001'
    owner = base/'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    inputs = [Path(__file__).resolve(), owner, base/'qualification_progress_062.json']
    def evidence(folder):
        path = base/folder/'assessment.json'
        value = json.loads(path.read_text())
        inputs.append(path)
        # Recheck receipt artifacts, including large matrices, before reporting.
        for name, expected in value.get('artifacts', {}).items():
            assert digest(Path(name)) == expected, name
        return value
    checks = {c:evidence(f'DCO_local_C_matrix_{c}_self_checks_001') for c in ['min','nom','max']}
    assert all(v['zero_wire_R_collapse_matches_owned_physical_operator_totals'] for v in checks.values())
    assert all(checks[c]['signed_global_passivity_numerical_check_passed'] for c in ['min','nom'])
    assert not checks['max']['signed_global_passivity_numerical_check_passed']
    transfer = evidence('DCO_self_C_support_transfer_001')
    extra = evidence('DCO_self_C_extra_support_GDS_geometry_001')
    assert extra['all_added_self_extra_supports_covered']
    assert extra['counts']['supports_checked'] == transfer['counts']['requires_direct_GDS_check'] == 66927
    startup = evidence('split_DC_initialization_controls_001')
    assert startup['native_saved_IC_UIC_linear_and_BSIM_transient_control_passed']
    candidate = evidence('DCO_domain_candidate_nom_001')
    assert candidate['source_matrix_numerical_passivity_check_passed']
    evidence('DCO_self_C_increment_identity_001')
    diagnosis = evidence('DCO_max_C_negative_mode_diagnosis_001')
    for corner, folder in [('nom','DCO_local_C_operators_nom_self_002'),('min','DCO_local_C_operators_min_self_001'),('max','DCO_local_C_operators_max_self_001')]:
        inputs.append(base/folder/'assessment.json')
        assert (base/folder/'assessment.json').is_file()
    live = []
    for p in Path('/proc').glob('[0-9]*'):
        try:
            kind = (p/'comm').read_text().strip()
            if kind in ['Xyce','ngspice','magicdnull']:
                row = process(int(p.name))
                if row['live']:
                    live.append(dict(kind=kind, **row))
        except (FileNotFoundError, ProcessLookupError):
            continue
    assert len(live) <= 4
    native = {}
    for folder in ['DCO_domain_nom_tt27_c0_f247_80ns_klu_001','DCO_domain_nom_tt27_c0_f247_C_free_DC_001']:
        path = base/folder/'status.json'
        native[folder] = json.loads(path.read_text())
        pid = native[folder].get('native_pid')
        if pid:
            native[folder]['process_at_observation'] = process(pid)
        manifest = base/folder/'input_manifest.json'
        inputs.append(manifest)
        if (base/folder/'assessment.json').exists():
            evidence(folder)
    stopped = base/'DCO_domain_nom_tt27_c0_f247_80ns_001/stopped_for_solver_configuration.json'
    assert stopped.exists()
    inputs.append(stopped)
    followup = dict(all_three_corrected_operator_compilations_completed=True,
        all_three_zero_R_conservation_checks_passed=True,
        numerical_passivity_passed_by_corner={c:v['signed_global_passivity_numerical_check_passed'] for c,v in checks.items()},
        normalized_minimum_eigenvalues_by_corner={c:v['normalized_minimum_eigenvalues'] for c,v in checks.items()},
        maximum_C_negative_modes=diagnosis['maximum_C_matrix_negative_energy_modes_confirmed'],
        all_added_nominal_self_C_supports_covered_by_prior_or_direct_GDS_evidence=True,
        prior_GDS_union_covered=transfer['counts']['covered_by_prior_GDS_verified_union'],
        direct_added_supports_GDS_passed=66927,
        nominal_complete_domain_diagnostic_SPICE_exported=True,
        saved_IC_startup_control_passed=True,
        maximum_control_waveform_difference_V=max(startup['maximum_interpolated_waveform_differences_V']),
        native_points=native, current_native_engines=live,
        previous_default_solver_case_stopped_with_configuration_receipt=str(stopped.relative_to(root)),
        original_owner=str(owner.relative_to(root)), original_deadline_uptime=deadline,
        budget_restarted=False, runtime_model_eligible=False, release_qualified=False, adopted=False)
    for name, expected in {
        'verification/release_requirements_400mhz.json':'02911569a2538d8b4d6c3139decdf7ec4d7c33bf2cbad85eed442947c0022b52',
        'verification/release_plan_400mhz.json':'2d6d5ed4404df842d64d42d68ebe593e4f627e65b4f90aaa48bef5f991e94b02'}.items():
        assert digest(root/name) == expected
        inputs.append(root/name)
    previous = json.loads((base/'qualification_progress_062.json').read_text())
    previous.update(observed_utc=datetime.now(timezone.utc).isoformat(),
        classification='corrected_min_and_nom_C_pass_max_C_negative_modes_diagnosed_nominal_native_and_exact_DC_checks_active',
        restored_self_C_operator_followup=followup,
        evidence_sha256={str(p.relative_to(root)):digest(p) for p in inputs},
        active_distributed_RC_followups=[], native_analog_jobs=live, native_analog_count=len(live),
        current_native_CAD_and_analog_engines=live,
        release_qualified=False, adopted=False, physical_whole_pll_passes=0,
        next_actions=[
            'Trace remaining maximum-C negative-energy modes to their actual owned physical operators; do not clamp eigenvalues or export the rejected corner',
            'Finish same-owner C-free DC and compare saved bias or startup against the preserved full-C native run before changing initialization',
            'Complete actual DCO numerical/spatial and parent-feed/load qualification and frozen calibration, 15PVT timing, reset/CDC, wholePLL, physical and reproducibility gates'])
    snapshot = base/'qualification_progress_063.json'
    assert not snapshot.exists()
    save(snapshot, previous)
    overview = root/'build/timing450/implementation_assessment.json'
    state = json.loads(overview.read_text())
    state.update(latest_400mhz_qualification_progress=str(snapshot.relative_to(root)),
        active_400mhz_restored_self_C_operator_followup=followup,
        active_400mhz_distributed_RC_followups=[],
        active_400mhz_distributed_RC_check=dict(owner=str(owner.relative_to(root)),
            state='min_nom_C_pass_max_C_nonpass_nominal_native_and_DC_checks',
            deadline_uptime=deadline, native_analog_jobs=len(live), release_qualified=False),
        release_qualified=False, selected=False, timing_closure_complete=False)
    save(overview,state)
    print('Progress063: min/nom pass; max two negative-energy modes; added nominal geometry passed; native diagnostics tracked.')


if __name__ == '__main__':
    main()
