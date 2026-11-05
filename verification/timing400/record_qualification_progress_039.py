#!/usr/bin/env python3
"""Record individually classified corner warnings and bounded floating loads."""
from datetime import datetime,timezone
from pathlib import Path
import time
from record_qualification_progress_031 import ROOT,BASE,read,digest,write


def main():
    names=['qualification_progress_038.json',
        'poly_metal_full_capacitance_corner_collection_001/min_feedback.log',
        'corner_diode_warning_geometry_001/assessment.json','poly_metal_min_corner_feedback_002/assessment.json',
        'poly_metal_full_capacitance_corner_collection_002/owner.json',
        'poly_metal_full_capacitance_corner_collection_002/input_manifest.json',
        'poly_metal_full_capacitance_corner_collection_002/min/network/assessment.json',
        'poly_metal_full_capacitance_corner_collection_002/min/positive/assessment.json',
        'floating_capacitance_reduction_controls_001/assessment.json',
        'floating_capacitance_reduction_001/assessment.json','numerical_environment_001.json',
        'return_fine_output_buffer_candidate_001/plan.json','return_fine_output_buffer_connectivity_001/assessment.json']
    paths=[BASE/n for n in names]+[Path(__file__).resolve(),ROOT/'verification/release_requirements_400mhz.json',
        ROOT/'verification/release_plan_400mhz.json']
    prior=read(paths[0]);feedback=read(paths[3]);minimum=read(paths[6]);positive=read(paths[7])
    reduction=read(paths[9]);candidate=read(paths[11]);connectivity=read(paths[12])
    assert feedback['full_corner_warning_classification_passed'] and feedback['full_feedback_entries']==3014
    assert feedback['unclassified_feedback_entries']==0
    assert minimum['component_record_counts']['X_MOS']==99720
    assert minimum['component_record_counts']['X_DIODE']==726 and minimum['component_record_counts']['X_RESISTOR']==16
    assert not minimum['missing_parent_nodes'] and not minimum['negative_capacitor_examples']
    assert positive['retained_positive_capacitors']==21384654 and positive['removed_exact_zero_capacitors']==27970382
    assert read(paths[8])['exact_decimal_series_values_enclosed'] and reduction['all_requested_width_targets_met']
    assert reduction['graph']['n']==2095561 and reduction['graph']['unanchored_nodes']==0
    assert connectivity['all771_instance_connections_preserved'] and connectivity['only_changed_cell']=='out_buf'
    queue=BASE/'poly_metal_full_capacitance_corners_002'
    qs=read(queue/'status.json');case=queue/qs['corner'];ns=read(case/'status.json')
    native_pid=ns['native_pid'];proc=Path('/proc')/str(native_pid)
    assert (proc/'stat').read_text().rsplit(')',1)[1].split()[0]!='Z'
    assert 'magicdnull' in (proc/'cmdline').read_bytes().decode()
    collector_owner=read(BASE/'poly_metal_full_capacitance_corner_collection_002/owner.json')
    cp=Path('/proc')/str(collector_owner['runner_pid'])
    assert (cp/'stat').read_text().rsplit(')',1)[1].split()[0]!='Z'
    analog=[];boot=time.clock_gettime(time.CLOCK_BOOTTIME)
    for p in Path('/proc').glob('[0-9]*'):
        try:
            if (p/'comm').read_text().strip()!='Xyce' or (p/'stat').read_text().rsplit(')',1)[1].split()[0]=='Z':continue
            argv=[s.decode() for s in (p/'cmdline').read_bytes().split(b'\0') if s]
            directory=Path(argv[-1]).parent;owner=read(directory/'owner.json')
            deadline=owner.get('absolute_deadline_uptime',owner.get('deadline_uptime'));assert deadline>boot
            row=dict(pid=int(p.name),argv=argv,owner=owner,remaining_budget_s=deadline-boot)
            waves=list(directory.glob('*.prn'))
            if len(waves)==1:
                with waves[0].open('rb') as f:
                    f.seek(max(0,waves[0].stat().st_size-4096));lines=f.read().split(b'\n')[:-1]
                complete=[x.split() for x in lines if len(x.split())>=3 and x.split()[0].isdigit()]
                if complete:row.update(latest_complete_wave_row_time_ns=float(complete[-1][1])*1e9,waveform_observation_only=True)
            analog.append(row)
        except (FileNotFoundError,ProcessLookupError):continue
    assert len(analog)<=4
    floating=dict(directory='build/timing400/release_001/floating_capacitance_reduction_001',
        nominal_positive_capacitors=22512429,floating_nodes=2095561,floating_components=174,
        unanchored_nodes=0,other_active_boundaries_held_incrementally_fixed=True,wire_resistance_assumed_zero=True,
        nonlinear_device_charge_excluded=True,positive_capacitor_energy_and_residual_bounds_used=True,
        native_series_control_decimal_solutions_enclosed=True,wrong_trials_have_wide_intervals=True,
        negative_capacitor_controls_rejected=True,all_requested_absolute_widths_ff_met=1e-4,
        target_bounds=reduction['targets'],full_physical_load_or_timing_qualified=False,model_adopted=False)
    buffer=dict(top=candidate['candidate_top'],source=candidate['candidate_source'],
        based_on_certified_wire_only_nominal_load_diagnostic=True,actual_functional_overload_proven=False,
        old_nominal_buf1_max_capacitance_pf=.130015,new_nominal_buf8_max_capacitance_pf=5.,
        only_changed_existing_cell='out_buf',all771_connections_preserved=True,other770_cell_types_preserved=True,
        return_fine_loads_preserved=80,physical_layout_started=False,native_analog_started=False,
        all_nominal15pvt_and_four_mode_checks_required=True,release_qualified=False,adopted=False)
    corners=dict(first_reader_nonpass_due_to_unhandled_diode_boundary_diagnostics=True,
        initial_failed_assessment_retained=True,diode_diffusions_individually_located=726,
        min_warnings_classified=3014,min_decap_matches=2288,min_diode_boundary_matches=726,
        min_native_mos_wrappers=99720,min_native_diode_wrappers=726,min_native_resistor_wrappers=16,
        min_positive_capacitors=21384654,min_zero_records_removed=27970382,min_parent_nodes=359,
        min_negative_capacitors=0,max_source_status_at_observation=qs,verified_max_native_pid=native_pid,
        collector_owner=collector_owner,collector_status=read(BASE/'poly_metal_full_capacitance_corner_collection_002/status.json'),
        no_source_native_reruns=True,full_corner_comparison_pending=True,full_rc_enclosure_qualified=False)
    progress=dict(observed_utc=datetime.now(timezone.utc).isoformat(),classification='floating_load_bounds_and_corner_warning_progress_not_release',
        evidence_sha256={str(p.relative_to(ROOT)):digest(p) for p in paths},latest_candidate=prior['latest_candidate'],
        expanded_capacitance=prior['expanded_capacitance'],current_parent_wire_rc=prior['current_parent_wire_rc'],
        fom_reference=prior['fom_reference'],current_diode_geometry_work=prior['current_diode_geometry_work'],
        full_capacitance_corners=corners,floating_capacitance=floating,stronger_output_experiment=buffer,
        native_analog_jobs=sorted(analog,key=lambda r:r['pid']),native_analog_count=len(analog),
        hs_diode_status=read(BASE/'hs_diode_geometry_comparison_001/status.json'),
        original_absolute_deadlines_retained=True,required_nominal_15pvt_scope_unchanged=True,
        physical_whole_pll_cases_passed=0,physical_ordered_mode_change_cases_passed=0,release_qualified=False,adopted=False,
        next_actions=['Collect max-cap corner and compare all normalized device statements and parent diagonals before RC model adoption',
            'Finish the queued HS diode geometry comparisons when a guarded analog slot is free',
            'Use numerical floating-load bounds with nonlinear/interface and material/RC enclosure; do not treat them as full timing signoff',
            'Collect TT100 coarse14 endpoints and corrected duration probes; decide new physical DCO experiment from terminal evidence',
            'Complete qualified nominal15PVT timing/calibration/interfaces,60 wholePLL cases and ordered mode changes',
            'Complete supply/noise, physical power/jitter/area and documented integration release gates'])
    snapshot=BASE/'qualification_progress_039.json';assert not snapshot.exists();write(snapshot,progress)
    overview=ROOT/'build/timing450/implementation_assessment.json';data=read(overview)
    data['latest_400mhz_qualification_progress']=str(snapshot.relative_to(ROOT))
    data['active_400mhz_full_capacitance_corners']=corners
    data['active_400mhz_floating_capacitance_bounds']=floating
    data['active_400mhz_stronger_output_experiment']=buffer
    for key in ['release_qualified','selected','timing_closure_complete']:data[key]=False
    write(overview,data)
    print('Progress039: all min-corner diagnostics individually classified, floating KCL bounds complete, isolated buf8 variant structurally audited; full qualification open.')


if __name__=='__main__':main()
