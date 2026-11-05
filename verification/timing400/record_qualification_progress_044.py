#!/usr/bin/env python3
"""Record full-DCO C trace accounting and native substrate-context discovery."""
from datetime import datetime,timezone
from pathlib import Path
from record_qualification_progress_031 import ROOT,BASE,read,digest,write
from check_compact_clock_tree import verify


def main():
    names=['qualification_progress_043.json','magic_full_C_trace_patch_001/assessment.json',
        'magic_full_C_trace_build_001/assessment.json','magic_full_C_trace_default_controls_001/assessment.json',
        'magic_full_C_trace_controls_001/status.json','magic_full_C_trace_controls_002/failure.json',
        'magic_full_C_trace_patch_002/assessment.json','magic_full_C_trace_patch_derivation_002/assessment.json',
        'magic_full_C_trace_build_002/assessment.json','magic_full_C_trace_default_controls_002/assessment.json',
        'magic_full_C_trace_controls_003/assessment.json','DCO_full_C_trace_controls_001/failure.json',
        'magic_full_C_trace_patch_003/assessment.json','magic_full_C_trace_build_003/assessment.json',
        'magic_full_C_trace_default_controls_003/assessment.json','magic_full_C_trace_controls_004/assessment.json',
        'magic_full_C_trace_stream_reader_controls_001/assessment.json','DCO_full_C_trace_controls_002/assessment.json',
        'fresh_DCO_nominal_source_comparison_001/assessment.json','fresh_DCO_nominal_source_comparison_001/comparison.json',
        'fresh_DCO_nominal_source_difference_001/assessment.json','DCO_resistance_enabled_C_context_001/assessment.json',
        'DCO_resistance_enabled_C_context_002/assessment.json','magic_resistance_substrate_semantics_001/assessment.json',
        'DCO_native_R_node_geometry_001/assessment.json','DCO_native_R_node_geometry_002/assessment.json',
        'magic_RC_substrate_C_patch_001/assessment.json']
    paths=[BASE/n for n in names]+[Path(__file__).resolve(),ROOT/'verification/release_requirements_400mhz.json',ROOT/'verification/release_plan_400mhz.json']
    assert digest(paths[-2])=='02911569a2538d8b4d6c3139decdf7ec4d7c33bf2cbad85eed442947c0022b52'
    assert digest(paths[-1])=='2d6d5ed4404df842d64d42d68ebe593e4f627e65b4f90aaa48bef5f991e94b02'
    trace=verify(BASE/'DCO_full_C_trace_controls_002/assessment.json');assert trace['full_DCO_trace_accounting_passed']
    default=verify(BASE/'magic_full_C_trace_default_controls_003/assessment.json');assert default['installed_and_isolated_C_devices_feedback_equal']
    controls=verify(BASE/'magic_full_C_trace_controls_004/assessment.json');assert controls['full_geometry_trace_accounting_controls_passed']
    reader=verify(BASE/'magic_full_C_trace_stream_reader_controls_001/assessment.json');assert reader['stream_reader_controls_passed']
    nom=verify(BASE/'DCO_resistance_enabled_C_context_001/assessment.json');other=verify(BASE/'DCO_resistance_enabled_C_context_002/assessment.json')
    assert nom['full_DCO_trace_accounting_passed'] and other['full_DCO_trace_accounting_passed']
    assert nom['results'][0]['retained_pre_RC_exact_positive_C_matrix_equal']
    semantics=verify(BASE/'magic_resistance_substrate_semantics_001/assessment.json')
    geometry=verify(BASE/'DCO_native_R_node_geometry_002/assessment.json')
    difference=read(BASE/'fresh_DCO_nominal_source_difference_001/assessment.json')
    assert difference['changed_C_pairs']==1753 and difference['maximum_C_difference_ff']=='0.5114'
    analog=[]
    for p in Path('/proc').glob('[0-9]*'):
        try:
            if (p/'comm').read_text().strip() not in ['Xyce','ngspice'] or (p/'stat').read_text().rsplit(')',1)[1].split()[0]=='Z':continue
            argv=[x.decode() for x in (p/'cmdline').read_bytes().split(b'\0') if x];analog.append(dict(pid=int(p.name),argv=argv))
        except (FileNotFoundError,ProcessLookupError):continue
    assert len(analog)<=4
    work=dict(private_trace_file_and_completion_marker=True,default_native_CAD_runs=24,
        four_small_controls_native_CAD_runs=12,stream_reader_agrees_exactly_on12_retained_native_logs=True,
        full_DCO_C_only_native_CAD_runs=9,full_DCO_RC_enabled_native_CAD_runs=6,
        C_only_case_results=trace['results'],RC_enabled_case_results=nom['results']+other['results'],
        all_native_device_and_C_comparisons_against_installed_passed=True,
        all_signed_trace_C_matrices_reconstructed_with_native_print_and_arithmetic_allowances=True,
        full_DCO_unlocated_output_clamp_events=0,raw_signed_and_support_records_retained=True,
        malformed_shared_log_attempts_retained=True,invalid_temporary_fringe_support_fixed=True,
        actual_GDS_support_positions_and_junction_distribution_qualified=False,
        spatial_RC_and_transient_error_qualified=False,parent_full_layout_trace_qualified=False,
        installed_extractor_replaced=False,old_DCO_RC_model_still_disqualified=True,model_adopted=False)
    context=dict(native_R_enabled_and_C_only_prepare_substrate_differently=True,
        upstream_context_source_semantics_pinned=True,PDK_technology_files_identical=True,
        nominal_C_only_vs_retained_R_context_changed_pairs=1753,maximum_nominal_C_difference_ff='0.5114',
        exported_transistor_models_parameters_and_ports_equal=True,
        R_enabled_nominal_exactly_recovers_retained_pre_RC_C=True,
        R_enabled_min_nom_max_trace_accounting_passed=True,
        full_C_only_parent_views_not_yet_proven_equivalent_to_native_RC_substrate_context=True,
        new_opt_in_C_only_RC_substrate_patch_prepared=True,new_opt_in_mode_native_controls_passed=False,
        bulk_and_well_R_geometry_and_impedance_qualified=False,
        native_R_coordinate_survey=dict(records=geometry['retained_native_R_nodes'],
            unique_exported_nodes=geometry['exported_R_MOS_and_port_nodes'],
            all_exported_nodes_have_retained_coordinates=geometry['all_exported_nodes_have_retained_native_coordinates'],
            classifications=geometry['classification_counts'],
            all_exported_nonbody_coordinates_matched=False,unmatched_nonbody_original_conductor='VGND'),
        original_absolute_CAD_deadline_uptime=3136114.566309955,total_budget_restarted=False,
        physical_RC_or_release_qualified=False)
    prior=read(BASE/'qualification_progress_043.json')
    progress={k:v for k,v in prior.items() if k not in ['observed_utc','classification','evidence_sha256','next_actions','native_analog_jobs','native_analog_count']}
    progress.update(observed_utc=datetime.now(timezone.utc).isoformat(),
        classification='full_DCO_trace_accounting_proven_and_RC_substrate_context_difference_isolated_not_release',
        evidence_sha256={str(p.relative_to(ROOT)):digest(p) for p in paths},
        full_geometry_C_trace_work=work,RC_substrate_context_work=context,native_analog_jobs=analog,native_analog_count=len(analog),
        release_qualified=False,adopted=False,physical_whole_pll_passes=0,
        next_actions=[
            'Validate opt-in RC substrate preparation without full wire extraction against installed R-enabled native DCO at all3 RC corners',
            'Use a proven common substrate context for C and R; never assume the old C-only parent network is interchangeable',
            'Resolve retained bulk/well and34 VGND internal coordinate supports; qualify C and junction spatial allocation and transient error',
            'Only then obtain fresh100/250/300/400 native range/calibration evidence; old-model ranges cannot select a redesign',
            'Complete qualified nominal15PVT timing/interfaces,60 physical wholePLL cases, ordered mode changes and remaining frozen release gates'])
    progress['C_localization_method_work'].update(full_geometry_contribution_trace_still_required=False,
        full_geometry_contribution_trace_validated_on_DCO=True,parent_full_layout_contribution_trace_still_required=True)
    snapshot=BASE/'qualification_progress_044.json';assert not snapshot.exists();write(snapshot,progress)
    overview=ROOT/'build/timing450/implementation_assessment.json';data=read(overview)
    data['latest_400mhz_qualification_progress']=str(snapshot.relative_to(ROOT))
    data['active_400mhz_full_geometry_C_trace_work']=work;data['active_400mhz_RC_substrate_context_work']=context
    data['active_400mhz_C_localization_method_work']=progress['C_localization_method_work']
    for key in ['release_qualified','selected','timing_closure_complete']:data[key]=False
    write(overview,data)
    print('Progress044: full DCO C traces recover native matrices at3 corners; nominal RC context matches original exactly; substrate/bulk/spatial qualification remains open. Zero qualified physical wholePLL cases.')


if __name__=='__main__':main()
