#!/usr/bin/env python3
"""Record nominal-wrapper work and charge-preserving RC control reconstruction."""
from datetime import datetime,timezone
from pathlib import Path
import time
from record_qualification_progress_031 import ROOT,BASE,read,digest,write


def alive(pid,marker):
    p=Path('/proc')/str(pid)
    return (p/'stat').read_text().rsplit(')',1)[1].split()[0]!='Z' and marker in (p/'cmdline').read_bytes().decode()


def main():
    names=['qualification_progress_040.json','narrow_mos_corner_exports_001/assessment.json',
        'poly_metal_full_nominal_wrapper_001/owner.json','poly_metal_full_nominal_wrapper_001/input_manifest.json',
        'nominal_wrapper_capacitance_collection_001/owner.json','nominal_wrapper_capacitance_collection_001/input_manifest.json',
        'driven_distributed_rc_coupling_controls_004/assessment.json',
        'single_pass_distributed_rc_coupling_audit_002/assessment.json',
        'driven_distributed_rc_coupling_controls_005/assessment.json',
        'automatic_distributed_rc_coupling_audit_001/assessment.json',
        'rc_extraction_source_analysis_001/assessment.json','charge_preserving_rc_controls_002/assessment.json']
    paths=[BASE/n for n in names]+[Path(__file__).resolve(),ROOT/'verification/release_requirements_400mhz.json',
        ROOT/'verification/release_plan_400mhz.json']
    prior=read(paths[0]);narrow=read(paths[1]);source=read(paths[10]);rebuilt=read(paths[11])
    assert narrow['native_devices_each']==28 and narrow['special_nfet_name_changes_per_cell']==4
    assert narrow['orig_and_nominal_wrapper_complete_capacitor_matrices_identical']
    assert narrow['all_three_wrapper_style_native_devices_identical']
    assert source['both_native_paths_fail_complete_capacitor_matrix_preservation']
    assert rebuilt['exact_collapsed_capacitor_matrices_preserved'] and rebuilt['all_capacitors_nonnegative']
    assert rebuilt['native_R_MOS_and_port_records_preserved'] and rebuilt['wrong_conductor_negative_control_rejected']
    nominal_owner=read(paths[2]);nominal_status=read(BASE/'poly_metal_full_nominal_wrapper_001/status.json')
    collector_owner=read(paths[4]);collector_status=read(BASE/'nominal_wrapper_capacitance_collection_001/status.json')
    assert alive(nominal_owner['runner_pid'],'run_full_layout_nominal_wrapper_capacitance.py')
    assert alive(nominal_status['native_pid'],'magicdnull')
    assert alive(collector_owner['runner_pid'],'collect_nominal_wrapper_capacitance.py')
    assert nominal_owner['deadline_uptime']==collector_owner['deadline_uptime']==3136114.566309955
    analog=[];boot=time.clock_gettime(time.CLOCK_BOOTTIME)
    for p in Path('/proc').glob('[0-9]*'):
        try:
            comm=(p/'comm').read_text().strip()
            if comm not in ['Xyce','ngspice'] or (p/'stat').read_text().rsplit(')',1)[1].split()[0]=='Z':continue
            argv=[s.decode() for s in (p/'cmdline').read_bytes().split(b'\0') if s]
            row=dict(pid=int(p.name),argv=argv)
            if comm=='Xyce':
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
    progress={k:v for k,v in prior.items() if k not in ['observed_utc','classification','evidence_sha256','next_actions']}
    wrapper=dict(actual_detector_FF_type='sky130_fd_sc_hd__dfrtp_1',native_control_cases=4,
        native_MOS_per_FF=28,special_model_names_per_FF=4,orig_and_nominal_wrapper_C_matrices_identical=True,
        three_wrapper_style_native_device_sets_identical=True,models_aliased=False,
        full_layout_nominal_wrapper_owner=nominal_owner,full_layout_nominal_wrapper_status=nominal_status,
        verified_native_pid=nominal_status['native_pid'],collector_owner=collector_owner,collector_status=collector_status,
        original_absolute_deadline_retained=True,full_layout_comparison_pending=True,
        runtime_model_qualified=False,model_adopted=False)
    rc=dict(matching_upstream_version='8.3.623',source_commit=source['upstream_commit'],
        binary_source_equivalence_proven=False,manual_only_and_automatic_only_native_controls_complete=True,
        manual_capacitor_matrix_changes_per_case=[11,12],automatic_capacitor_matrix_changes_per_case=[5,6],
        automatic_path_does_not_lose_internal_coupling_pairs=True,both_paths_export_negative_C=True,
        duplicate_stage_removed_in_single_pass_controls=True,
        default_C_export_approved_for_full_layout=False,
        reconstructed_control_cases=2,retained_native_R_per_reconstructed_case=31,
        reconstructed_MOS_and_port_records_unchanged=True,reconstructed_negative_capacitors=0,
        exact_collapsed_original_C_matrix_restored=True,wrong_conductor_attachment_rejected=True,
        original_lumped_C_placement_on_same_conductor_MOS_terminal_used=True,
        exact_original_seed_location_preservation_proven=False,
        physical_distributed_C_geometry_qualified=False,transient_error_enclosure_qualified=False,
        full_layout_RC_qualified=False,runtime_model_qualified=False,model_adopted=False)
    hs_status=read(BASE/'hs_diode_geometry_comparison_001/status.json')
    hs_owner=read(BASE/'hs_diode_geometry_comparison_001/run_owner.json')
    assert alive(hs_owner['runner_pid'],'run_hs_diode_comparison.py')
    progress.update(observed_utc=datetime.now(timezone.utc).isoformat(),
        classification='nominal_wrapper_native_started_and_RC_charge_reconstruction_controls_not_release',
        evidence_sha256={str(p.relative_to(ROOT)):digest(p) for p in paths},
        nominal_wrapper_model_work=wrapper,rc_export_path_isolation_and_reconstruction=rc,
        native_analog_jobs=sorted(analog,key=lambda r:r['pid']),native_analog_count=len(analog),
        hs_diode_status=hs_status,
        next_actions=[
            'Collect and assess the live full-layout nominal wrapper export under its original CAD budget',
            'Validate spatial C distribution or independent conservative transient bounds before RC model adoption',
            'Collect TT100 coarse14 endpoints and corrected duration probes; decide physical DCO experiment from terminal evidence',
            'Finish queued HS diode geometry comparisons within the original check budget',
            'Complete material/RC/nonlinear interfaces and nominal15PVT timing/calibration,60 wholePLL cases and ordered mode changes',
            'Complete supply/noise, physical jitter/power/area and integration release gates'])
    progress['current_diode_geometry_work']['status_at_observation']=hs_status
    snapshot=BASE/'qualification_progress_041.json';assert not snapshot.exists();write(snapshot,progress)
    overview=ROOT/'build/timing450/implementation_assessment.json';data=read(overview)
    data['latest_400mhz_qualification_progress']=str(snapshot.relative_to(ROOT))
    data['active_400mhz_nominal_wrapper_model_work']=wrapper
    data['active_400mhz_RC_path_isolation_and_reconstruction']=rc
    for key in ['release_qualified','selected','timing_closure_complete']:data[key]=False
    write(overview,data)
    print('Progress041: nominal wrapper extraction/collector verified live; manual/automatic RC failures isolated; positive-C reconstruction passes small controls. Full qualification remains open.')


if __name__=='__main__':main()
