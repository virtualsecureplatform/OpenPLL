#!/usr/bin/env python3
"""Record native R-material provenance and minimum-corner assembled C assessment."""
from datetime import datetime,timezone
from decimal import Decimal
from pathlib import Path
from record_qualification_progress_031 import ROOT,BASE,read,digest,write
from check_compact_clock_tree import verify
from record_qualification_progress_045 import process


def main():
    names=['qualification_progress_045.json','magic_R_node_trace_patch_001/assessment.json','magic_R_node_trace_build_001/assessment.json',
        'DCO_R_node_trace_controls_001/status.json','DCO_R_node_trace_controls_001/isolated/comparison.json',
        'DCO_R_default_network_renaming_audit_001/assessment.json','DCO_R_default_network_renaming_audit_002/assessment.json',
        'DCO_R_default_network_renaming_audit_003/assessment.json','DCO_R_default_network_renaming_audit_004/assessment.json',
        'DCO_R_default_network_renaming_audit_004/comparison.json','native_R_graph_comparison_fault_controls_001/assessment.json',
        'DCO_R_node_trace_controls_002/assessment.json','DCO_R_node_trace_controls_002/trace/network_comparison.json',
        'DCO_R_node_provenance_inspection_002/assessment.json','DCO_R_node_provenance_inspection_002/summary.json',
        'DCO_bulk_material_support_001/assessment.json','DCO_bulk_supply_origin_support_001/assessment.json',
        'RC_substrate_capacitance_collection_001/min/status.json','RC_substrate_capacitance_collection_001/min/feedback.log',
        'RC_substrate_old_feedback_assessor_retirement_001/assessment.json',
        'poly_metal_full_RC_substrate_capacitance_001/min/native_completion.json',
        'RC_substrate_capacitance_collection_002/min/assessment.json','RC_substrate_capacitance_collection_002/min/feedback/assessment.json',
        'RC_substrate_capacitance_collection_002/min/network/assessment.json','RC_substrate_capacitance_collection_002/min/positive/assessment.json']
    paths=[BASE/n for n in names]+[Path(__file__).resolve(),ROOT/'verification/release_requirements_400mhz.json',ROOT/'verification/release_plan_400mhz.json']
    assert digest(paths[-2])=='02911569a2538d8b4d6c3139decdf7ec4d7c33bf2cbad85eed442947c0022b52'
    assert digest(paths[-1])=='2d6d5ed4404df842d64d42d68ebe593e4f627e65b4f90aaa48bef5f991e94b02'
    base_graph=read(BASE/'DCO_R_default_network_renaming_audit_004/comparison.json')
    assert base_graph['bijective_mapping_proven'] and not base_graph['R_C_differences']['R'] and base_graph['unchanged_device_parameters_and_mapped_terminals']
    faults=verify(BASE/'native_R_graph_comparison_fault_controls_001/assessment.json');assert faults['native_R_comparison_fault_controls_passed']
    traced=verify(BASE/'DCO_R_node_trace_controls_002/assessment.json');assert traced['R_graph_values_and_MOS_terminals_preserved_under_bijective_renaming']
    assert traced['pre_RC_C_matrix_preserved_within_native_print_intervals'] and traced['native_pre_RC_devices_identical']
    interpreted=verify(BASE/'DCO_R_node_provenance_inspection_002/assessment.json')
    material=verify(BASE/'DCO_bulk_material_support_001/assessment.json');origins=verify(BASE/'DCO_bulk_supply_origin_support_001/assessment.json')
    assert material['actual_GDS_ground34_pwell_junction_membership_passed'] and origins['all_supply_origin_records_on_actual_declared_port_conductor']
    feedback=verify(BASE/'RC_substrate_capacitance_collection_002/min/feedback/assessment.json')
    network=verify(BASE/'RC_substrate_capacitance_collection_002/min/network/assessment.json')
    positive=verify(BASE/'RC_substrate_capacitance_collection_002/min/positive/assessment.json')
    assert feedback['full_feedback_entries']==2288 and feedback['native_diode_position_area_perimeter_and_body_matches']==726
    assert network['component_record_counts']=={'X':100462,'X_MOS':99720,'X_DIODE':726,'X_RESISTOR':16,'C':49355117,'zero_capacitors':27970463}
    assert not network['missing_parent_nodes'] and not network['negative_capacitor_examples']
    assert positive['retained_positive_capacitors']==21384654 and positive['no_nonzero_capacitor_values_changed']
    proof=dict(native_DCO_reference_runs=2,native_DCO_material_trace_runs=1,
        native_generated_node_names_and_internal_representative_coordinates_unstable=True,
        default_renamed_nodes=base_graph['renamed_nodes'],default_internal_coordinate_changes=len(base_graph['internal_node_coordinate_changes']),
        bijective_R_graph_mapping_nodes=base_graph['mapped_nodes'],graph_symmetry_candidates_tested=base_graph['candidate_count'],
        exact_R_branch_multiplicity_and_MOS_terminals_preserved=True,R_values_match_within_per_branch_native_print_intervals=True,
        independent_numeric_topology_and_terminal_location_fault_controls_passed=True,
        invalid_backannotated_C_not_adopted=True,default_backannotated_C_print_interval_difference_pairs=45,
        maximum_default_backannotated_C_difference_ff=str(max(abs(Decimal(r['delta']))*Decimal('1e15') for r in base_graph['R_C_differences']['C'])),
        native_original_pre_RC_C_and_devices_preserved=True,
        native_provenance_groups=interpreted['groups_in_native_log'],last_explicit_all_net_groups=interpreted['last_all_net_groups'],
        node_coordinate_records_recovered_exactly=interpreted['native_node_coordinate_records'],
        ground34_native_origins={'junction':34},ground34_native_incident_materials=['pwell'],
        ground34_actual_GDS_pwell_membership_proven=True,internal_MOS_body_records_in_expected_GDS_wells=8204,
        four_supply_origin_records_on_actual_M4_M5_port_conductors=True,
        bulk_R_magnitude_impedance_enclosure_qualified=False,
        supply_origin_coordinates_are_local_physical_MOS_body_positions=False,
        lumped_body_connections_C_junction_allocation_and_transient_error_qualified=False,
        old_RC_model_still_disqualified=True,runtime_model_adopted=False)
    minimum=dict(native_CAD_terminal=True,feedback_entries=2288,all_decap_warnings_individually_located=True,
        all726_native_diode_geometry_and_body_connections_checked=True,diode_boundary_warnings=0,
        native_devices=100462,MOS=99720,diodes=726,intrinsic_resistor_wrappers=16,active_device_nodes=33669,
        parent_nets_with_capacitance=359,capacitor_records=49355117,negative_capacitors=0,
        exact_zero_records_removed=27970463,positive_C_records_retained=21384654,
        exact_C_values_floating_branches_and_devices_preserved=True,
        old3014_warning_assessment_failure_retained=True,old_queued_assessors_retired_without_native_signals=True,
        source_native_CAD_retried=False,release_or_model_qualified=False)
    jobs=[]
    for corner in ['min','nom','max']:
        source=BASE/'poly_metal_full_RC_substrate_capacitance_001'/corner
        collector=BASE/'RC_substrate_capacitance_collection_002'/corner
        comparison=BASE/'RC_substrate_C_context_matrix_comparison_001'/corner
        owner=read(source/'owner.json');co=read(collector/'owner.json');po=read(comparison/'owner.json')
        assert owner['deadline_uptime']==co['deadline_uptime']==po['deadline_uptime']==3136114.566309955
        paths.extend([source/'owner.json',collector/'owner.json',comparison/'owner.json'])
        state=read(source/'status.json')
        jobs.append(dict(corner=corner,source=str(source.relative_to(ROOT)),collector=str(collector.relative_to(ROOT)),comparison=str(comparison.relative_to(ROOT)),
            observed_source_state=state,source_runner=process(owner['runner_pid']),native=process(state.get('native_pid',-1)),
            assessor=process(co['runner_pid']),C_comparator=process(po['runner_pid']),original_deadline_uptime=owner['deadline_uptime']))
    analog=[]
    for p in Path('/proc').glob('[0-9]*'):
        try:
            if (p/'comm').read_text().strip() in ['Xyce','ngspice']:
                r=process(int(p.name))
                if r['live']:analog.append(r)
        except (FileNotFoundError,ProcessLookupError):continue
    assert len(analog)<=4
    prior=read(BASE/'qualification_progress_045.json')
    progress={k:v for k,v in prior.items() if k not in ['observed_utc','classification','evidence_sha256','next_actions','native_analog_jobs','native_analog_count']}
    progress.update(observed_utc=datetime.now(timezone.utc).isoformat(),
        classification='native_R_material_provenance_and_minimum_RC_full_C_assessment_completed_not_release',
        evidence_sha256={str(p.relative_to(ROOT)):digest(p) for p in paths},native_R_material_provenance_work=proof,
        RC_substrate_full_C_minimum_assessment=minimum,current_full_RC_C_jobs=jobs,native_analog_jobs=analog,native_analog_count=len(analog),
        release_qualified=False,adopted=False,physical_whole_pll_passes=0,
        next_actions=[
            'Complete remaining max/nom full-layout RC-substrate C jobs and all three exact old/new C-context comparisons under the original09:44UTC deadline',
            'Verify actual native device parameters across corners and retain the2288-warning RC-context audit; never restart completed native extractions',
            'Use proven R material/support metadata to qualify spatial capacitor and junction allocation, supply-origin body connections, bulk impedance and transient error',
            'Only then obtain fresh qualified100/250/300/400 native ranges and calibration; the retired RC model cannot select a redesign',
            'Complete nominal15PVT timing/interfaces,60 physical wholePLL cases, ordered mode changes and remaining frozen release gates'])
    progress['RC_substrate_context_work'].update(native_R_ground34_material_interpretation_and_actual_GDS_support_completed=True,
        old_unresolved_body4_are_verified_supply_origin_records=True,ground34_no_longer_unclassified_metal_coordinates=True,
        physical_bulk_impedance_and_body_junction_models_still_unqualified=True,
        minimum_full_C_assessment_completed=True,attached_assessor_generation=2)
    snapshot=BASE/'qualification_progress_046.json';assert not snapshot.exists();write(snapshot,progress)
    overview=ROOT/'build/timing450/implementation_assessment.json';data=read(overview)
    data['latest_400mhz_qualification_progress']=str(snapshot.relative_to(ROOT))
    data['active_400mhz_native_R_material_provenance_work']=proof
    data['active_400mhz_full_RC_C_minimum_assessment']=minimum
    data['active_400mhz_RC_substrate_context_work']=progress['RC_substrate_context_work']
    for key in ['release_qualified','selected','timing_closure_complete']:data[key]=False
    write(overview,data)
    print('Progress046: native R topology and original C preserved;34 pwell junctions,8204 internal body locations and4 supply origins explained. Full min C assessment passed; max/nom and exact context comparisons continue. Release remains false.')


if __name__=='__main__':main()
