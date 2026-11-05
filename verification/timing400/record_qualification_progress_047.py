#!/usr/bin/env python3
"""Record completed three-corner common-substrate C checks and buffer-only candidate."""
from datetime import datetime,timezone
from decimal import Decimal
from pathlib import Path
from record_qualification_progress_031 import ROOT,BASE,read,digest,write
from check_compact_clock_tree import verify
from record_qualification_progress_045 import process


def main():
    names=['qualification_progress_046.json','RC_substrate_floating_capacitance_bounds_001/assessment.json',
        'magic_upstream_685_build_001/status.json','magic_upstream_685_build_001/configure.log',
        'magic_upstream_685_build_002/assessment.json','upstream_685_DCO_RC_charge_control_001/assessment.json',
        'base_output_buffer_candidate_001/plan.json','base_output_buffer_connectivity_001/assessment.json',
        'DCO_C_R_support_inventory_001/assessment.json','DCO_C_R_support_inventory_001/summary.json']
    paths=[BASE/n for n in names]+[Path(__file__).resolve(),ROOT/'verification/release_requirements_400mhz.json',ROOT/'verification/release_plan_400mhz.json']
    assert digest(paths[-2])=='02911569a2538d8b4d6c3139decdf7ec4d7c33bf2cbad85eed442947c0022b52'
    assert digest(paths[-1])=='2d6d5ed4404df842d64d42d68ebe593e4f627e65b4f90aaa48bef5f991e94b02'
    bounds=verify(BASE/'RC_substrate_floating_capacitance_bounds_001/assessment.json')
    assert bounds['original_floating_certificate_verified'] and bounds['same_actual_device_node_and_boundary_sets_proven']
    assert bounds['changed_floating_edges']==0 and len(bounds['targets'])==3
    candidate=read(BASE/'base_output_buffer_candidate_001/plan.json');connectivity=verify(BASE/'base_output_buffer_connectivity_001/assessment.json')
    assert connectivity['all691_instance_connections_preserved'] and connectivity['other690_cell_types_preserved']
    assert not connectivity['return_fine_bank_added'] and connectivity['original_C1_fine_load_bank_preserved']==160
    for p,d in candidate['input_sha256'].items():assert digest(Path(p))==d,p
    assert digest(Path(candidate['candidate_source']))==candidate['candidate_source_sha256']
    assert digest(Path(candidate['candidate_config']))==candidate['candidate_config_sha256']
    config=Path(candidate['candidate_config']);paths.extend([Path(candidate['candidate_source']),config,config.parent/'pin_order.cfg',config.parent/'no_clock.sdc'])
    newer=verify(BASE/'upstream_685_DCO_RC_charge_control_001/assessment.json')
    assert not newer['capacitor_matrix_preserved_within_per_pair_print_intervals'] and not newer['MOS_models_parameters_and_zero_wire_R_connections_preserved']
    inventory=verify(BASE/'DCO_C_R_support_inventory_001/assessment.json');support=read(BASE/'DCO_C_R_support_inventory_001/summary.json')
    corners=[]
    for corner,positive_count in [('min',21384654),('nom',22512429),('max',23107833)]:
        source=BASE/'poly_metal_full_RC_substrate_capacitance_001'/corner
        collected=BASE/'RC_substrate_capacitance_collection_002'/corner
        old_positive=(BASE/'nominal_wrapper_capacitance_collection_001/positive' if corner=='nom' else BASE/'poly_metal_full_capacitance_corner_collection_002'/corner/'positive')
        for p in [source/'native_completion.json',collected/'assessment.json',collected/'feedback/assessment.json',
            collected/'network/assessment.json',collected/'positive/assessment.json',old_positive/'assessment.json',
            BASE/'RC_substrate_C_context_matrix_comparison_001'/corner/'assessment.json',BASE/'RC_substrate_C_context_matrix_difference_001'/corner/'assessment.json']:
            paths.append(p)
        native=read(source/'native_completion.json');collection=read(collected/'assessment.json')
        feedback=read(collected/'feedback/assessment.json');network=read(collected/'network/assessment.json')
        positive=read(collected/'positive/assessment.json');old=read(old_positive/'assessment.json')
        diff=read(BASE/'RC_substrate_C_context_matrix_difference_001'/corner/'assessment.json')
        assert native['native_extraction_completed'] and collection['warning_network_and_exact_zero_cleanup_terminal']
        assert feedback['full_corner_warning_classification_passed'] and feedback['full_feedback_entries']==2288
        assert feedback['native_diode_position_area_perimeter_and_body_matches']==726
        assert network['parent_nodes_with_capacitance']==359 and not network['negative_capacitor_examples']
        assert network['component_record_counts']['X_MOS']==99720 and network['component_record_counts']['X_DIODE']==726 and network['component_record_counts']['X_RESISTOR']==16
        assert positive['retained_positive_capacitors']==positive_count and positive['no_nonzero_capacitor_values_changed']
        assert old['unchanged_device_and_continuation_sha256']==positive['unchanged_device_and_continuation_sha256']
        assert diff['changed_nonself_energy_pairs']>0 and not diff['exact_parsed_nonself_C_matrix_equivalent']
        diagonal=read(BASE/'RC_substrate_C_context_matrix_difference_001'/corner/'parent_diagonal_deltas.json')
        corners.append(dict(corner=corner,native_and_assessment_terminal=True,devices=network['component_record_counts'],
            active_device_nodes=network['active_device_nodes'],all359_parent_nets_present=True,negative_C=0,
            zero_C_removed=positive['removed_exact_zero_capacitors'],positive_C=positive_count,feedback_entries=2288,
            all_diode_geometry_body_checks_passed=True,device_and_continuation_bytes_identical_to_corresponding_old_context=True,
            changed_C_pairs=diff['changed_nonself_energy_pairs'],maximum_pair_delta_ff=diff['maximum_nonself_pair_delta_ff'],
            absolute_pair_delta_sum_ff=diff['sum_absolute_nonself_pair_deltas_ff'],changed_self_pairs=diff['changed_zero_energy_self_pairs'],
            critical_parent_diagonal_deltas_ff={k:diagonal.get(k,'0') for k in ['PLLOUT','REFCLK','BBPD_RESET_N']}))
    analog=[]
    for p in Path('/proc').glob('[0-9]*'):
        try:
            if (p/'comm').read_text().strip() in ['Xyce','ngspice']:
                r=process(int(p.name))
                if r['live']:analog.append(r)
        except (FileNotFoundError,ProcessLookupError):continue
    assert len(analog)<=4
    prior=read(BASE/'qualification_progress_046.json')
    progress={k:v for k,v in prior.items() if k not in ['observed_utc','classification','evidence_sha256','next_actions','native_analog_jobs','native_analog_count']}
    common=dict(three_RC_corners_completed_before_original_deadline=True,original_deadline_uptime=3136114.566309955,
        native_CAD_retries=0,total_budget_restarted=False,corners=corners,
        old_C_only_and_native_RC_substrate_networks_proven_different=True,
        nominal_changed_edges_touching_floating_nodes=0,nominal_floating_energy_certificate_transferred_without_resolve=True,
        nominal_target_wire_C_bounds=bounds['targets'],zero_wire_R_and_other_boundaries_fixed_assumptions_retained=True,
        nonlinear_charge_and_actual_FOM_material_and_distributed_RC_qualified=False,model_adopted=False)
    stock=dict(version='8.3.685',commit='bed8d4ff84333767aa923d469d339cd05c56a00a',isolated_unmodified_build_completed=True,
        premature_configure_attempt_retained=True,nominal_DCO_native_charge_control_completed=True,
        same_RC_substrate_context_and_zero_C_threshold_used=True,wire_R=newer['wire_R'],
        original_C_cards=newer['original_C_records'],backannotated_C_cards=newer['backannotated_C_records'],
        changed_C_pairs_outside_local_print_intervals=newer['changed_C_pairs_outside_print_intervals'],
        two_global_junction_parameter_records_still_lost=True,RC_model_qualification_passed=False,adopted=False,
        installed_extractor_or_golden_Xyce_changed=False)
    buf=dict(candidate_top=candidate['candidate_top'],source=candidate['candidate_source'],config=candidate['candidate_config'],
        only_changed_instance='out_buf',old_cell='sky130_fd_sc_hd__buf_1',new_cell='sky130_fd_sc_hd__buf_8',
        total_cells=691,all_instance_connections_and_other690_types_preserved=True,C1_fine_bank=160,return_fine_bank_added=False,
        public_ports_encoding_and_library_logic_function_A_preserved=True,
        certified_nominal_wire_only_diagnostic_contains_buf1_domain_overrun=True,
        buf8_nominal_library_load_domain_contains_this_diagnostic=True,
        actual_functional_overload_proven=False,physical_layout_or_native_analog_started=False,
        frequency_range_input_load_and_loaded_interface_qualified=False,adopted=False)
    progress.update(observed_utc=datetime.now(timezone.utc).isoformat(),
        classification='three_corner_RC_context_C_checks_complete_newer_stock_RC_rejected_and_buffer_only_candidate_audited_not_release',
        evidence_sha256={str(p.relative_to(ROOT)):digest(p) for p in paths},full_RC_substrate_C_completion=common,
        newer_stock_extractor_RC_test=stock,base_output_buffer_only_candidate=buf,C_to_R_support_inventory=support,
        native_analog_jobs=analog,native_analog_count=len(analog),release_qualified=False,adopted=False,physical_whole_pll_passes=0,
        next_actions=[
            'Use the complete C/R support inventory to construct physically consistent C placement and account for intrinsic resistor body capacitance',
            'Qualify local junction allocation, body connections at supply origins, bulk/supply impedance and transient error; both stock native backannotated C outputs remain rejected',
            'Generate a fresh eligible runtime model, then obtain100/250/300/400 nominal15PVT ranges, calibration, reset reachability and duration/timestep convergence',
            'Keep buf8-only and RF80+buf8 candidates separate; decide physical implementation from qualified original-model range and loaded-interface evidence',
            'Complete qualified nominal15PVT timing,60 physical wholePLL cases, ordered mode changes and remaining frozen release gates'])
    progress['RC_substrate_context_work'].update(full_parent_all3_RC_context_C_assessments_terminal=True,
        full_parent_exact_C_context_differences_measured=True,nominal_wire_C_bounds_updated_by_exact_energy_shift=True,
        physical_runtime_RC_model_qualified=False)
    snapshot=BASE/'qualification_progress_047.json';assert not snapshot.exists();write(snapshot,progress)
    overview=ROOT/'build/timing450/implementation_assessment.json';data=read(overview)
    data['latest_400mhz_qualification_progress']=str(snapshot.relative_to(ROOT))
    data['active_400mhz_full_RC_substrate_C_completion']=common;data['active_400mhz_base_output_buffer_only_candidate']=buf
    data['active_400mhz_newer_stock_extractor_RC_test']=stock;data['active_400mhz_C_to_R_support_inventory']=support
    data['active_400mhz_RC_substrate_context_work']=progress['RC_substrate_context_work']
    for key in ['release_qualified','selected','timing_closure_complete']:data[key]=False
    write(overview,data)
    print('Progress047: all3 full RC-context C checks and exact comparisons completed; updated nominal load bounds; newer native RC still fails;691-cell buf8-only candidate audited. Runtime RC/PLL/timing qualification remains open.')


if __name__=='__main__':main()
