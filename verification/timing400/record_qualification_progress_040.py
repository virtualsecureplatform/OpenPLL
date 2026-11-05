#!/usr/bin/env python3
"""Record completed C corners and rejected default distributed-C export."""
from datetime import datetime,timezone
from pathlib import Path
import time
from record_qualification_progress_031 import ROOT,BASE,read,digest,write


def main():
    names=['qualification_progress_039.json',
        'poly_metal_full_capacitance_corners_002/native_completion.json',
        'poly_metal_full_capacitance_corner_collection_002/assessment.json',
        'poly_metal_full_capacitance_corner_comparison_002/assessment.json',
        'poly_metal_full_capacitance_corner_collection_002/max/network/assessment.json',
        'poly_metal_full_capacitance_corner_collection_002/max/positive/assessment.json',
        'poly_metal_full_capacitance_corner_collection_002/max/feedback/assessment.json',
        'corner_model_name_difference_audit_001/assessment.json',
        'driven_distributed_rc_coupling_controls_001/assessment.json',
        'driven_distributed_rc_coupling_controls_002/assessment.json',
        'driven_distributed_rc_coupling_controls_003/assessment.json',
        'distributed_rc_coupling_audit_002/assessment.json',
        'distributed_rc_coupling_audit_002/comparison.json']
    paths=[BASE/n for n in names]+[Path(__file__).resolve(),ROOT/'verification/release_requirements_400mhz.json',
        ROOT/'verification/release_plan_400mhz.json']
    prior=read(paths[0]);comparison=read(paths[3]);maximum=read(paths[4]);positive=read(paths[5])
    feedback=read(paths[6]);models=read(paths[7]);rc=read(paths[11]);rcdetails=read(paths[12])
    assert comparison['parent_nodes_compared']==359 and not comparison['parent_diagonal_corner_order_inversions']
    assert not comparison['normalized_device_statements_all_preserved']
    assert maximum['component_record_counts']['X_MOS']==99720 and maximum['component_record_counts']['X_DIODE']==726
    assert maximum['component_record_counts']['X_RESISTOR']==16 and not maximum['negative_capacitor_examples']
    assert positive['retained_positive_capacitors']==23107833 and positive['removed_exact_zero_capacitors']==26267595
    assert feedback['full_feedback_entries']==3014 and feedback['unclassified_feedback_entries']==0
    assert models['model_name_differences_per_corner']==8 and models['all_other_native_device_fields_preserved']
    assert not rc['complete_capacitor_matrix_preserved'] and not rc['default_extresist_C_export_approved_for_full_layout']
    assert rc['exact_matrix_positive_control_passed'] and rc['missing_coupling_negative_control_rejected']
    assert all(len(row['negative_exported_capacitors'])==4 for row in rcdetails.values())
    analog=[];boot=time.clock_gettime(time.CLOCK_BOOTTIME)
    for p in Path('/proc').glob('[0-9]*'):
        try:
            if (p/'comm').read_text().strip() not in ['Xyce','ngspice'] or (p/'stat').read_text().rsplit(')',1)[1].split()[0]=='Z':continue
            argv=[s.decode() for s in (p/'cmdline').read_bytes().split(b'\0') if s]
            row=dict(pid=int(p.name),argv=argv)
            if (p/'comm').read_text().strip()=='Xyce':
                directory=Path(argv[-1]).parent;owner=read(directory/'owner.json')
                deadline=owner.get('absolute_deadline_uptime',owner.get('deadline_uptime'));assert deadline>boot
                row.update(owner=owner,remaining_budget_s=deadline-boot)
                waves=list(directory.glob('*.prn'))
                if len(waves)==1:
                    with waves[0].open('rb') as f:
                        f.seek(max(0,waves[0].stat().st_size-4096));lines=f.read().split(b'\n')[:-1]
                    complete=[x.split() for x in lines if len(x.split())>=3 and x.split()[0].isdigit()]
                    if complete:row.update(latest_complete_wave_row_time_ns=float(complete[-1][1])*1e9,waveform_observation_only=True)
            analog.append(row)
        except (FileNotFoundError,ProcessLookupError):continue
    assert len(analog)<=4
    corners=dict(all_three_native_capacitance_extractions_completed=True,
        all_corner_assessments_terminal=True,no_source_native_reruns=True,
        max_native_mos_wrappers=99720,max_native_diode_wrappers=726,max_native_resistor_wrappers=16,
        max_positive_capacitors=23107833,max_zero_records_removed=26267595,
        max_warnings_classified=3014,max_decap_matches=2288,max_diode_boundary_matches=726,
        parent_diagonals_compared=359,parent_diagonal_order_inversions=0,
        model_name_differences_per_corner=8,model_names_preserved=False,
        all_other_native_device_fields_preserved=True,
        differences_explained_by_installed_width_selection=True,ordinary_and_special_models_aliased=False,
        special_model_matching_length_um=.15,special_model_matching_width_um=.36,
        nominal_wrapper_model_scope_requires_validation=True,
        reported_diagonals_are_effective_loads=False,full_rc_enclosure_qualified=False)
    distributed=dict(real_driver_controls_completed=2,explicit_unique_ports_verified=True,
        prior_wire_only_control_stopped_without_completion=True,
        prior_driven_control_port_index_errors_retained=True,
        duplicate_port_control_signal11_retained=True,
        cause_of_signal11_not_independently_proven=True,
        corrected_single_driver_port_controls_terminal=True,
        complete_capacitor_matrix_preserved=False,
        changed_branch_pairs=rc['changed_branch_pairs'],
        negative_exported_C_per_control=4,
        negative_exported_values_ff=[r['value_ff'] for r in rcdetails['floating_tile']['negative_exported_capacitors']],
        exact_matrix_positive_control_passed=True,missing_coupling_negative_control_rejected=True,
        default_extresist_C_export_approved_for_full_layout=False,
        small_control_passivity_asserted=False,full_layout_RC_qualified=False,model_adopted=False)
    progress={k:prior[k] for k in ['latest_candidate','expanded_capacitance','current_parent_wire_rc',
        'fom_reference','current_diode_geometry_work','floating_capacitance','stronger_output_experiment']}
    progress.update(observed_utc=datetime.now(timezone.utc).isoformat(),
        classification='completed_C_corner_comparison_and_rejected_default_distributed_C_export_not_release',
        evidence_sha256={str(p.relative_to(ROOT)):digest(p) for p in paths},
        full_capacitance_corners=corners,distributed_rc_controls=distributed,
        native_analog_jobs=sorted(analog,key=lambda r:r['pid']),native_analog_count=len(analog),
        hs_diode_status=read(BASE/'hs_diode_geometry_comparison_001/status.json'),
        original_absolute_deadlines_retained=True,required_nominal_15pvt_scope_unchanged=True,
        physical_whole_pll_cases_passed=0,physical_ordered_mode_change_cases_passed=0,
        release_qualified=False,adopted=False,
        next_actions=[
            'Validate nominal wrapper model scope for eight narrow NFETs; do not alias ordinary/special models',
            'Use independently checked wire R and C geometry mapping; default extresist C export failed preservation controls',
            'Collect TT100 coarse14 endpoints and corrected duration probes; decide physical DCO experiment from terminal evidence',
            'Finish HS diode geometry comparison when a guarded analog slot becomes free',
            'Complete material/RC and nonlinear interface enclosure, nominal15PVT qualification,60 wholePLL cases and mode changes',
            'Complete supply/noise, physical power/jitter/area and integration release gates'])
    progress['current_diode_geometry_work']['status_at_observation']=progress['hs_diode_status']
    snapshot=BASE/'qualification_progress_040.json';assert not snapshot.exists();write(snapshot,progress)
    overview=ROOT/'build/timing450/implementation_assessment.json';data=read(overview)
    data['latest_400mhz_qualification_progress']=str(snapshot.relative_to(ROOT))
    data['active_400mhz_full_capacitance_corners']=corners
    data['active_400mhz_distributed_rc_controls']=distributed
    for key in ['release_qualified','selected','timing_closure_complete']:data[key]=False
    write(overview,data)
    print('Progress040: three C corners compared; eight model names classified; default RC-C export rejected by native controls. Release remains unqualified.')


if __name__=='__main__':main()
