#!/usr/bin/env python3
"""Record actual DCO model invalidation, diode compatibility and RC repair data."""
from datetime import datetime,timezone
from pathlib import Path
import time
from record_qualification_progress_031 import ROOT,BASE,read,digest,write


def main():
    names=['qualification_progress_041.json','active_dco_lumped_capacitance_export_001/assessment.json',
        'active_dco_rc_capacitance_audit_001/assessment.json','unqualified_dco_RC_retirement_001/assessment.json',
        'DCO_RC_model_invalidation_001/assessment.json','hs_diode_geometry_comparison_001/assessment.json',
        'hs_diode_geometry_comparison_001/native_completion.json','hs_diode_geometry_comparison_001/comparison_metrics.json',
        'checked_diode_geometry_translation_controls_001/assessment.json',
        'checked_diode_geometry_translation_cli_001/tt27.translation.json',
        'current_DCO_intercell_wire_rc_001/native_completion.json','DCO_intercell_wire_rc_audit_001/assessment.json',
        'DCO_signal_pin_geometry_001/assessment.json','DCO_intercell_wire_rc_geometry_001/assessment.json',
        'DCO_wire_rc_coordinate_classification_001/assessment.json','charge_preserving_DCO_RC_prototype_001/assessment.json',
        'poly_metal_full_nominal_wrapper_001/native_completion.json','nominal_wrapper_capacitance_collection_001/assessment.json',
        'nominal_wrapper_capacitance_comparison_001/assessment.json']
    paths=[BASE/n for n in names]+[Path(__file__).resolve(),ROOT/'scripts/translate_sky130_checked_diode_geometries.py',
        ROOT/'verification/timing400/compare_unordered_nominal_capacitance.py',
        ROOT/'verification/release_requirements_400mhz.json',ROOT/'verification/release_plan_400mhz.json']
    prior=read(paths[0]);audit=read(paths[2]);retired=read(paths[3]);invalid=read(paths[4])
    hs=read(paths[5]);metrics=read(paths[7]);translator=read(paths[8]);cli=read(paths[9]);wire=read(paths[11])
    geom=read(paths[14]);prototype=read(paths[15]);nominal=read(paths[18])
    assert audit['changed_capacitor_branch_pairs']==1799 and audit['completely_lost_capacitor_branch_pairs']==256
    assert audit['negative_intermediate_rnode_C']==126 and audit['changed_device_parameter_records']==2
    assert retired['all_native_processes_stopped_verified'] and retired['retired_native_jobs']==4
    for row in retired['jobs']:
        p=Path('/proc')/str(row['pid'])
        assert not p.exists() or (p/'stat').read_text().rsplit(')',1)[1].split()[0]=='Z'
    assert hs['model_equivalence_screen_passed'] and hs['electrical_cases']==15 and hs['noise_bias_cases']==75
    assert translator['actual_native_diode_cards']==726 and translator['fixed_temperature_corner_models_checked']==15
    assert cli['translated_by_geometry']=={'hs':724,'hd':2}
    assert wire['routed_SPEF_nets_each_corner']==505 and wire['all_multiterminal_DEF_nets_covered'] and not wire['path_corner_order_inversions']
    assert geom['RC_coordinates_classified']==8413 and geom['unclassified_coordinates']==0
    assert prototype['exact_zero_R_capacitor_matrix_preserved'] and prototype['all_C_nonnegative']
    assert prototype['retained_native_wire_resistors']==97616 and prototype['original_C_count']==35051
    assert nominal['all_three_wrapper_native_device_sets_identical'] and not nominal['exact_ordered_capacitor_records_preserved']
    canonical_pids=[];analog=[]
    for p in Path('/proc').glob('[0-9]*'):
        try:
            if (p/'stat').read_text().rsplit(')',1)[1].split()[0]=='Z':continue
            argv=[x.decode() for x in (p/'cmdline').read_bytes().split(b'\0') if x]
            if any(x.endswith('/compare_unordered_nominal_capacitance.py') or x=='verification/timing400/compare_unordered_nominal_capacitance.py' for x in argv):
                canonical_pids.append(int(p.name))
            if (p/'comm').read_text().strip() in ['Xyce','ngspice']:analog.append(dict(pid=int(p.name),argv=argv))
        except (FileNotFoundError,ProcessLookupError):continue
    assert len(analog)<=4 and len(canonical_pids)==1
    current_comparison=BASE/'unordered_nominal_capacitance_comparison_001'
    canonical_status=read(current_comparison/'status.json') if (current_comparison/'status.json').exists() else dict(state='verifying_existing_provenance_before_output_creation')
    progress={k:v for k,v in prior.items() if k not in ['observed_utc','classification','evidence_sha256','next_actions','native_analog_jobs','native_analog_count']}
    dco=dict(exact_model_sha256=invalid['invalidated_model_sha256'],model_disqualified_for_physical_range_and_calibration=True,
        same_threshold_changed_C_pairs_above_conservative_rounding_allowance=1799,completely_lost_C_pairs_above_allowance=256,
        negative_native_intermediate_C=126,changed_junction_parameter_records=2,
        native_R_reduction_preserves_bad_export_C=True,retired_native_jobs=4,all_retired_native_processes_stopped_verified=True,
        partial_results_retained=True,identical_retries_started=False,
        previous_TT_brackets_are_diagnostics_of_invalidated_model=True,original_design_range_failure_proven=False,
        return_fine_physical_variant_decision_requires_fresh_qualified_model_evidence=True,
        prototype_native_wire_R=97616,prototype_original_C=35051,prototype_MOS=8618,prototype_intrinsic_R=2,
        prototype_zero_R_C_and_device_parameter_limit_exact=True,prototype_negative_C=0,
        prototype_spatial_C_distribution_and_transient_error_qualified=False,prototype_adopted=False)
    diode=dict(required_native_analyses_completed=360,HD_geometry_instances=2,HS_geometry_instances=724,
        HS_electrical_PVT_cases_passed=15,HS_noise_bias_cases_passed=75,
        reference_simulator='ngspice47',golden_simulator='upstream Xyce',HS_geometry_model_comparison_passed=True,
        HS_max_errors={k:max(r['errors'][k] for r in metrics['electrical']) for k in metrics['electrical'][0]['errors']},
        HS_max_noise_PSD_relative_error=max(r['noise_psd_error'] for r in metrics['noise']),
        two_geometry_translator_actual_cards_checked=726,translator_native_matched_fixed_T_models=15,
        translator_scope_and_input_fault_controls_rejected=translator['unknown_geometry_and_unsupported_input_controls_rejected'],
        all_current_diode_geometries_within_checked_model_compatibility_scope=True,
        assembled_physical_PLL_model_integrated=False,release_qualified=False)
    resistance=dict(routed_DEF_nets_matched=505,unrouted_singleton_DEF_nets=453,multiple_driver_nets=wire['multiple_driver_nets'],
        corners=['min','nom','max'],all_R_positive_and_connected=True,path_corner_order_inversions=0,
        actual_GDS_DEF_placements_matched=1736,actual_signal_terminals_correlated=2071,actual_signal_nets_correlated=956,
        body_only_unrouted_public_ports=['VPB','VNB'],physical_internal_R_coordinates=2641,
        physical_terminal_coordinates=5418,verified_virtual_terminal_coordinates=354,
        unclassified_coordinates=0,virtual_coordinates_are_physical_C_locations=False,
        C_distribution_and_cell_internal_R_qualified=False,model_adopted=False)
    wrapper=dict(full_layout_nominal_wrapper_native_and_collection_terminal=True,native_devices_each_RC_corner=100462,
        all_three_wrapper_native_device_sets_identical=True,orig_export_special_model_name_differences=8,
        exact_raw_ordered_C_export_preserved=False,C_matrix_equivalence_currently_unproven=True,
        canonical_unordered_positive_C_comparison_pid=canonical_pids[0],canonical_comparison_status=canonical_status,
        original_absolute_CAD_deadline_uptime=3136114.566309955,native_extractions_retried=False,
        physical_RC_enclosure_qualified=False,model_adopted=False)
    progress.update(observed_utc=datetime.now(timezone.utc).isoformat(),
        classification='actual_DCO_RC_model_invalidated_and_native_diode_compatibility_passed_with_repair_prototypes_not_release',
        evidence_sha256={str(p.relative_to(ROOT)):digest(p) for p in paths},
        DCO_model_invalidation_and_repair=dco,checked_diode_model_compatibility=diode,
        DCO_intercell_resistance=resistance,nominal_wrapper_model_work=wrapper,
        native_analog_jobs=analog,native_analog_count=len(analog),
        hs_diode_status=read(BASE/'hs_diode_geometry_comparison_001/status.json'),
        next_actions=[
            'Collect the live exact unordered nominal C comparison; preserve any real differences',
            'Qualify spatial capacitor distribution and transient-error bounds before any further long DCO native range/calibration sweep',
            'Use validated replacement models for fresh100/250/300/400 range/calibration evidence; prior brackets cannot select a physical variant',
            'Use the checked HD/HS translator only within its fixed-T/bias/frequency scope during physical-model integration',
            'Complete nominal15PVT timing/interfaces,60 physical wholePLL cases and ordered mode changes',
            'Complete material/RC enclosure, supply/noise, physical power/jitter/area and integration release gates'])
    progress['current_diode_geometry_work'].update(hs_geometry_comparison_passed=True,
        all_current_diode_geometries_qualified=False,model_compatibility_scope_checked=True,
        status_at_observation=progress['hs_diode_status'])
    snapshot=BASE/'qualification_progress_042.json';assert not snapshot.exists();write(snapshot,progress)
    overview=ROOT/'build/timing450/implementation_assessment.json';data=read(overview)
    data['latest_400mhz_qualification_progress']=str(snapshot.relative_to(ROOT))
    data['active_400mhz_DCO_model_invalidation_and_repair']=dco
    data['active_400mhz_checked_diode_model_compatibility']=diode
    data['active_400mhz_DCO_intercell_resistance']=resistance
    data['active_400mhz_nominal_wrapper_model_work']=wrapper
    for key in ['release_qualified','selected','timing_closure_complete']:data[key]=False
    write(overview,data)
    print('Progress042: actual DCO RC model invalidated and4native runs retired; HS15/75 comparisons pass; checked726-diode translator and full-DCO zero-R-consistent prototype prepared. Spatial RC and full release qualification remain open.')


if __name__=='__main__':main()
