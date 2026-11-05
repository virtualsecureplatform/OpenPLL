#!/usr/bin/env python3
"""Record local-kernel controls, nominal DCO pass and verified live follow-ups."""
from datetime import datetime, timezone
from pathlib import Path
import time
from check_compact_clock_tree import verify
from record_qualification_progress_031 import ROOT, BASE, read, digest, write
from record_qualification_progress_045 import process


def main():
    owner = BASE/'distributed_RC_model_qualification_001/owner.json'
    deadline = read(owner)['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    receipt_names = ['magic_C_kernel_source_preparation_001', 'magic_C_kernel_trace_patch_001',
        'magic_C_kernel_trace_build_002', 'magic_C_kernel_trace_controls_001',
        'magic_C_kernel_deadline_reader_controls_001', 'local_C_energy_integration_controls_001',
        'DCO_native_mesh_node_plane_inference_001']
    receipts = [BASE/n/'assessment.json' for n in receipt_names]
    preparation, patch, build, small, reader, energy, planes = [verify(p) for p in receipts]
    assert preparation['all_11_diagnostic_source_files_reproduced'] and not preparation['previous_source_modified']
    assert build['full_geometry_trace_build_completed'] and not build['installed_extractor_replaced']
    assert small['full_geometry_trace_accounting_controls_passed']
    assert small['local_kernel_integrals_and_event_alignment_controls_passed']
    assert reader['all12_completed_native_cases_equal_to_original_kernel_reader'] and reader['expired_deadline_rejected']
    assert all(v == 12 for v in reader['negative_control_case_counts'].values())
    assert energy['positive_uniform_patch_energy_integrator_controls_passed']
    assert planes['all_contact_and_single_tile_planes_uniquely_inferred']
    controller = BASE/'DCO_C_kernel_trace_controls_001'
    nom = next(r for r in read(controller/'comparison.json') if r['corner'] == 'nom')
    assert nom['native_matrix_reconstructed'] and nom['installed_RC_context_and_C_only_context_exact_C_devices_identical']
    assert nom['native_feedback_equal_without_running_R_pass']
    kernel = read(controller/'nom_trace/kernel_accounting.json')
    assert kernel['complete_ordered_kernel_to_contribution_alignment'] and kernel['local_kernel_integrals_reconstructed']
    assert kernel['counts']['events'] == 8297230 and kernel['counts']['split_rectangles'] == 0
    controller_owner = read(controller/'owner.json')
    assert controller_owner['deadline_uptime'] == deadline
    first = process(controller_owner['runner_pid'])
    assert first['live'] and any('check_DCO_C_kernel_trace.py' in a for a in first['argv'])
    geometry_dir = BASE/'DCO_complete_C_support_GDS_geometry_001'
    geometry_status = read(geometry_dir/'status.json')
    second = process(geometry_status['runner_pid'])
    assert second['live'] and any('check_DCO_complete_C_support_GDS_geometry.py' in a for a in second['argv'])
    assert geometry_status['deadline_uptime'] == deadline
    current = read(controller/'status.json')
    native = process(current.get('native_pid', -1))
    jobs = [dict(kind='DCO_three_RC_corner_charge_kernel_extraction_and_assessment',
        status_path=str((controller/'status.json').relative_to(ROOT)), status_at_observation=current,
        controller=first, native_process_at_observation=native, deadline_uptime=deadline),
        dict(kind='complete_nominal_C_support_GDS_geometry',
        status_path=str((geometry_dir/'status.json').relative_to(ROOT)), status_at_observation=geometry_status,
        controller=second, deadline_uptime=deadline)]
    native_engines = []
    for p in Path('/proc').glob('[0-9]*'):
        try:
            name = (p/'comm').read_text().strip()
            if name in ['Xyce', 'ngspice', 'magicdnull']:
                row = process(int(p.name))
                if row['live']:
                    native_engines.append(dict(kind=name, **row))
        except (FileNotFoundError, ProcessLookupError):
            continue
    assert not any(r['kind'] in ['Xyce', 'ngspice'] for r in native_engines)
    previous = BASE/'qualification_progress_057.json'
    requirements = ROOT/'verification/release_requirements_400mhz.json'
    plan = ROOT/'verification/release_plan_400mhz.json'
    assert digest(requirements) == '02911569a2538d8b4d6c3139decdf7ec4d7c33bf2cbad85eed442947c0022b52'
    assert digest(plan) == '2d6d5ed4404df842d64d42d68ebe593e4f627e65b4f90aaa48bef5f991e94b02'
    # Copy the completed nominal row; the shared comparison/status files remain
    # mutable while the same controller appends min/max. Do not pin those files.
    retained = BASE/'qualification_progress_058_evidence'
    retained.mkdir(exist_ok=False)
    write(retained/'nominal_completed_case.json', nom)
    evidence = dict(receipts={n: str(p.relative_to(ROOT)) for n, p in zip(receipt_names, receipts)},
        completed_native_small_case_corner_controls=12, small_negative_controls_all12_passed=True,
        nominal_DCO_local_kernels=kernel['counts']['kernels'], nominal_DCO_contributions=8297230,
        nominal_kernel_integrals_and_native_C_devices_feedback_passed=True,
        nominal_accumulator_residual_absolute_native_units=kernel['accumulator_and_clamp_residual_absolute_native_units'],
        min_max_DCO_charge_kernel_controls_complete=False, complete_nominal_support_GDS_geometry_complete=False,
        positive_uniform_patch_energy_integrator_and_average_voltage_counterexample_controls_passed=True,
        private_native_nodes_with_plane_associations=148346, contact_plane_pairs_inferred=35578,
        single_breakpoint_tile_planes_inferred=8997, physical_contact_sheet_error_qualified=False,
        full_C_assignment_and_signed_global_matrix_passivity_qualified=False,
        original_12h_deadline_uptime=deadline, total_budget_restarted=False,
        native_analog_runs_added=0, runtime_model_eligible=False, release_qualified=False, adopted=False)
    nom_dir = controller/'nom_trace'
    inputs = [Path(__file__).resolve(), previous, owner, requirements, plan, *receipts,
        retained/'nominal_completed_case.json', controller/'owner.json',
        nom_dir/'kernel_accounting.json', nom_dir/'kernels.log', nom_dir/'contributions.log',
        nom_dir/'surfaces.log', nom_dir/'control.spice', nom_dir/'surface_alignment.json',
        ROOT/'verification/timing400/check_DCO_C_kernel_trace.py',
        ROOT/'verification/timing400/check_DCO_complete_C_support_GDS_geometry.py',
        BASE/'magic_C_kernel_trace_build_001/status.json', BASE/'magic_C_kernel_trace_build_001/make.log']
    progress = dict(read(previous))
    progress.update(observed_utc=datetime.now(timezone.utc).isoformat(),
        classification='isolated_local_charge_kernel_controls_and_nominal_DCO_passed_min_max_and_complete_GDS_support_checks_live',
        evidence_sha256={str(p.relative_to(ROOT)): digest(p) for p in inputs},
        local_charge_kernel_qualification=evidence, active_distributed_RC_followups=jobs,
        native_analog_jobs=[], native_analog_count=0, current_native_CAD_and_analog_engines=native_engines,
        release_qualified=False, adopted=False, physical_whole_pll_passes=0)
    progress['next_actions'] = [
        'Poll the existing three-corner DCO kernel controller and complete-support GDS checker; preserve completed native runs if any assessor fails',
        'Assemble local kernel energy matrices on plane-aware private wire/single-tile/contact voltage fields using voltage products, not squared average voltages',
        'Verify full native matrix conservation, residual budget and signed global passivity; bound open-end/transverse/spatial and nonlinear/implicit-ground/intrinsic-resistor error',
        'Qualify min/max R values, external supply/driver feeds and308-pin adaptor, then complete frozen nominal1.8V/15PVT four-mode calibration, timing,60 wholePLL cases,mode changes and physical release gates']
    snapshot = BASE/'qualification_progress_058.json'
    assert not snapshot.exists()
    write(snapshot, progress)
    overview = ROOT/'build/timing450/implementation_assessment.json'
    current = read(overview)
    current['latest_400mhz_qualification_progress'] = str(snapshot.relative_to(ROOT))
    current['active_400mhz_local_charge_kernel_qualification'] = evidence
    current['active_400mhz_distributed_RC_followups'] = jobs
    current['active_400mhz_distributed_RC_check'] = dict(owner=str(owner.relative_to(ROOT)),
        state='local_kernel_nominal_DCO_passed_min_max_and_complete_GDS_geometry_checks_running',
        deadline_uptime=deadline, native_analog_jobs=0,
        status=str((controller/'status.json').relative_to(ROOT)),
        secondary_status=str((geometry_dir/'status.json').relative_to(ROOT)), release_qualified=False)
    for key in ['release_qualified', 'selected', 'timing_closure_complete']:
        current[key] = False
    write(overview, current)
    print('Progress058: isolated local kernels and nominal DCO passed; min/max kernel and complete GDS support checks verified live.')


if __name__ == '__main__':
    main()
