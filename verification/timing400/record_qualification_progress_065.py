#!/usr/bin/env python3
"""Record reconstructed max-C failure and controlled full-C saved-bias startup."""
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from compile_local_C_operators_v2 import digest,save
from record_qualification_progress_045 import process


def main():
    root=Path(__file__).resolve().parents[2]
    base=root/'build/timing400/release_001'
    owner=base/'distributed_RC_model_qualification_001/owner.json'
    deadline=json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME)<deadline
    proof=base/'DCO_self_C_support_corner_identity_001/assessment.json'
    identity=json.loads(proof.read_text())
    assert identity['all_added_self_support_geometries_identical_across_RC_corners']
    inputs=[Path(__file__).resolve(),owner,proof,base/'qualification_progress_064.json',
        Path(__file__).with_name('assess_DCO_domain_point_STD.py'),
        Path(__file__).with_name('trace_DCO_max_C_mode_energy.py')]
    for name,expected in {
        'verification/release_requirements_400mhz.json':'02911569a2538d8b4d6c3139decdf7ec4d7c33bf2cbad85eed442947c0022b52',
        'verification/release_plan_400mhz.json':'2d6d5ed4404df842d64d42d68ebe593e4f627e65b4f90aaa48bef5f991e94b02'}.items():
        assert digest(root/name)==expected
        inputs.append(root/name)
    jobs,engines=[],[]
    for p in Path('/proc').glob('[0-9]*'):
        try:
            args=[s.decode() for s in (p/'cmdline').read_bytes().split(b'\0') if s]
            if any(s.endswith('/inspect_DCO_max_C_mode_kernels.py') for s in args):
                row=process(int(p.name))
                if row['live']:jobs.append(row)
            if (p/'comm').read_text().strip() in ['Xyce','ngspice','magicdnull']:
                row=process(int(p.name))
                if row['live']:engines.append(row)
        except (FileNotFoundError,ProcessLookupError):
            continue
    assert len(engines)<=4
    statuses={}
    for folder in ['DCO_max_C_mode_kernel_inspection_001','DCO_domain_nom_tt27_c0_f247_80ns_klu_001',
                   'DCO_domain_nom_tt27_c0_f247_C_free_DC_001',
                   'DCO_domain_nom_tt27_c0_f247_zero_wire_R_DC_001',
                   'DCO_domain_nom_tt27_c0_f247_seeded_C_free_DC_001',
                   'DCO_domain_nom_tt27_c0_f247_seeded_C_free_DC_BASKER8_001',
                   'DCO_domain_nom_tt27_c0_f247_80ns_savedIC_001']:
        path=base/folder/'status.json'
        statuses[folder]=json.loads(path.read_text())
        assessment=base/folder/'assessment.json'
        if assessment.exists():inputs.append(assessment)
    energy_path=base/'DCO_max_C_mode_energy_trace_001/assessment.json'
    energy=json.loads(energy_path.read_text())
    assert energy['negative_energy_mode_reconstruction_passed'] and energy['all_owned_operators_checked']==18290414
    dc_path=base/'DCO_domain_nom_tt27_c0_f247_C_free_DC_001/assessment.json'
    assert json.loads(dc_path.read_text())['exact_C_free_DC_bias_completed']
    ideal_path=base/'DCO_domain_nom_tt27_c0_f247_zero_wire_R_DC_001/assessment.json'
    assert json.loads(ideal_path.read_text())['zero_wire_R_DC_diagnostic_completed']
    stop_path=base/'DCO_domain_nom_tt27_c0_f247_80ns_klu_001/stopped_for_saved_IC_initialization.json'
    stopped=json.loads(stop_path.read_text())
    assert stopped['complete_initial_voltage_coverage']==174508 and not stopped['budget_restarted']
    inputs.extend([energy_path,dc_path,ideal_path,stop_path,base/'DCO_DC_constraint_topology_001/assessment.json',
        Path(__file__).with_name('run_DCO_domain_point_v4.py'),Path(__file__).with_name('run_DCO_zero_wire_R_DC.py'),
        Path(__file__).with_name('run_DCO_seeded_C_free_DC.py'),Path(__file__).with_name('run_DCO_seeded_C_free_DC_BASKER.py'),
        Path(__file__).with_name('inspect_DCO_max_C_mode_kernels.py')])
    progress=json.loads((base/'qualification_progress_064.json').read_text())
    followup=progress['restored_self_C_operator_followup']
    followup.update(all_added_self_support_geometries_identical_across_RC_corners=True,
        all_added_self_supports_have_GDS_coverage_at_all_three_corners=True,
        support_geometry_identity_receipt=str(proof.relative_to(root)),
        active_check_statuses=statuses,current_native_engines=engines,
        native_points={k:v for k,v in statuses.items() if k.startswith('DCO_domain_')},
        prepared_completed_STD_native_point_reader='verification/timing400/assess_DCO_domain_point_STD.py',
        no_completed_native_case_repeated_for_output_reader_fix=True,
        maximum_C_negative_mode_all_operators_reconstructed=True,
        maximum_C_negative_mode_matrix_energy_native_units=energy['expected_matrix_energy_native_units'],
        maximum_C_negative_mode_reconstructed_energy_native_units=energy['reconstructed_operator_energy_native_units'],
        maximum_C_failed_mode_energy_by_category_native_units=energy['energy_by_category_native_units'],
        actual_physical_R_C_free_DC_completed=True, ideal_wire_DC_diagnostic_completed=True,
        saved_bias_node_voltages=174508, full_C_saved_IC_UIC_startup_control_passed=True,
        full_C_prior_KLU_startup_stopped_with_receipt=str(stop_path.relative_to(root)),
        full_C_physics_preserved_during_initialization_change=True,
        saved_IC_full_DCO_transient_startup_qualified=False,
        solver_comparison_uses_stock_upstream_BASKER_and_KLU=True,
        solver_comparison_requested_BASKER_OMP_threads=8,
        BASKER_parallel_speedup_established=False)
    progress.update(observed_utc=datetime.now(timezone.utc).isoformat(),
        classification='max_C_negative_energy_reconstructed_physical_R_DC_passed_controlled_saved_IC_full_C_transient_and_solver_comparisons_live',
        restored_self_C_operator_followup=followup,active_distributed_RC_followups=jobs,
        native_analog_jobs=engines,native_analog_count=len(engines),current_native_CAD_and_analog_engines=engines,
        evidence_sha256={str(p.relative_to(root)):digest(p) for p in inputs})
    snapshot=base/'qualification_progress_065.json'
    assert not snapshot.exists()
    save(snapshot,progress)
    overview=root/'build/timing450/implementation_assessment.json'
    state=json.loads(overview.read_text())
    state.update(latest_400mhz_qualification_progress=str(snapshot.relative_to(root)),
        active_400mhz_restored_self_C_operator_followup=followup,active_400mhz_distributed_RC_followups=jobs,
        release_qualified=False,selected=False,timing_closure_complete=False)
    state['active_400mhz_distributed_RC_check'].update(native_analog_jobs=len(engines),
        state='max_energy_failure_reconstructed_physical_DC_passed_saved_IC_full_C_diagnostic_live')
    save(overview,state)
    print('Progress065: physical-R DC passed, full-C saved-IC diagnostic live, max-C failure reconstructed from all operators.')


if __name__=='__main__':
    main()
