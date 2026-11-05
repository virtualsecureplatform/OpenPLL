#!/usr/bin/env python3
"""Record final filled geometry and the corrected electrical-model work."""
from datetime import datetime,timezone
import json
from pathlib import Path
from record_qualification_progress_031 import ROOT,BASE,read,digest,write


def main():
    final=BASE/'parent_dco_antenna_final_geometry_011/assessment.json';g=read(final)
    assert g['geometry_checks_passed'] and g['native_mos_only_antenna_feedback']==0
    assert g['pdk_density_failures']==g['assembled_magic_drc_rectangles']==g['independent_conservative_antenna_violations']==0
    assert g['assembled_lvs_passed'] and g['constrained_pdk_density_checks']==175
    assert not g['release_qualified'] and not g['physical_signoff_qualified']
    cap=BASE/'parent_filled_metal_capacitance_extract_002';status=read(cap/'status.json');owner=read(cap/'owner.json')
    view=BASE/'parent_filled_metal_capacitance_view_002/assessment.json';v=read(view)
    assert v['converted_metal_fill_purpose_layers_removed'] and v['drawing_and_fill_overlays_not_used']
    control=read(BASE/'fill_capacitance_control_audit_001/assessment.json')
    analog=[]
    for proc in Path('/proc').glob('[0-9]*'):
        try:
            if (proc/'comm').read_text().strip()!='Xyce':continue
            state=(proc/'stat').read_text().rsplit(')',1)[1].split()[0]
            if state=='Z':continue
            analog.append(dict(pid=int(proc.name),argv=[s.decode() for s in (proc/'cmdline').read_bytes().split(b'\0') if s]))
        except (FileNotFoundError,ProcessLookupError):continue
    assert len(analog)<=4
    paths=[Path(__file__).resolve(),Path(__file__).with_name('record_qualification_progress_031.py'),BASE/'qualification_progress_031.json',final,
        BASE/'parent_dco_antenna_layout_audit_filled_011/assessment.json',BASE/'parent_dco_antenna_density_audit_filled_011/assessment.json',
        BASE/'parent_dco_antenna_geometry_filled_011/antenna/assessment.json',BASE/'parent_dco_antenna_native_filled_011/native_completion.json',
        BASE/'openrcx_fill_source_audit_001/assessment.json',BASE/'fill_capacitance_control_audit_001/assessment.json',
        BASE/'fill_capacitance_mapped_control_001/assessment.json',BASE/'parent_filled_metal_capacitance_extract_001/superseded.json',
        BASE/'parent_filled_metal_capacitance_extract_001/native_completion.json',view,cap/'owner.json',cap/'input_manifest.json',
        ROOT/'verification/release_requirements_400mhz.json',ROOT/'verification/release_plan_400mhz.json']
    now=datetime.now(timezone.utc).isoformat()
    candidate=dict(route='build/timing400/release_001/parent_dco_antenna_targeted_011',
        stream='build/timing400/release_001/parent_dco_antenna_stream_filled_011',filled=True,
        final_geometry_audit=str(final.relative_to(ROOT)),gds_sha256=g['assembled_gds_sha256'],
        full_magic_drc_rectangles=0,assembled_lvs_passed=True,top_pins=55,parent_diodes=564,parent_well_taps=141,
        constrained_pdk_density_checks=175,pdk_density_failures=0,independent_forming_stages=13,
        independent_antenna_violations=0,native_mos_only_antenna_feedback=0,independent_port_probes=743,
        physical_shorts=0,missing_probes=0,split_logical_nets=0,exact_gds_bbox_nm=g['exact_gds_bbox_nm'],
        geometry_checks_passed=True,full_physical_signoff_qualified=False,rc_qualified=False,release_qualified=False,adopted=False)
    electrical=dict(stock_fill_purpose_ignored_in_control=True,overlay_of_fill_and_drawing_also_ignored_in_control=True,
        signal_to_floating_tile_coupling_f=control['signal_to_floating_tile_f'],
        floating_tile_effective_added_capacitance_f=control['floating_tile_effective_added_capacitance_f'],
        superseded_first_cad_diagnostic_retained=True,corrected_view=str(view.relative_to(ROOT)),
        corrected_view_replaces_converted_fill_purposes=True,parent_labels=359,
        current_extraction_directory=str(cap.relative_to(ROOT)),owner=owner,status_at_observation=status,
        native_analog_jobs_added=0,resistance_qualified=False,fom_poly_fill_coverage_qualified=False,
        full_capacitance_network_qualified=False,model_adopted=False)
    progress=dict(observed_utc=now,classification='geometry_progress_not_release',
        evidence_sha256={str(p.relative_to(ROOT)):digest(p) for p in paths},latest_candidate=candidate,electrical_extraction=electrical,
        native_warning_lines_retained=g['native_warning_lines'],native_analog_jobs=sorted(analog,key=lambda r:r['pid']),native_analog_count=len(analog),
        original_deadlines_retained=True,native_analog_jobs_restarted=0,required_nominal_15pvt_scope_unchanged=True,
        calibration_and_dynamic_models_qualified=False,qualified_timing_15pvt_complete=False,
        physical_whole_pll_cases_passed=0,physical_ordered_mode_change_cases_passed=0,release_qualified=False,adopted=False,
        next_actions=['Assess corrected full-GDS metal-fill capacitance extraction and all359 parent labels; preserve floating nodes',
            'Resolve remaining FOM/poly fill coverage, resistance, process/RC enclosure and interface loading before model adoption',
            'Collect TT100 endpoint results and both corrected160ns duration probes under their existing deadlines',
            'Complete qualified nominal15PVT timing, calibration, storage/reset/CDC interfaces and60 physical-model wholePLL cases plus ordered mode changes',
            'Complete final supply/noise, physical power/jitter/area and integration-assumption release gates'])
    snapshot=BASE/'qualification_progress_032.json';assert not snapshot.exists();write(snapshot,progress)
    overview=ROOT/'build/timing450/implementation_assessment.json';data=read(overview)
    data['latest_400mhz_qualification_progress']=str(snapshot.relative_to(ROOT))
    data['active_400mhz_parent_dco_antenna_route'].update(observed_utc=now,latest_candidate=candidate,
        last_full_drc_lvs_passing_candidate='build/timing400/release_001/parent_dco_antenna_layout_audit_filled_011/assessment.json',
        physical_checks=dict(terminal_geometry_checks_passed=True,final_geometry_audit=str(final.relative_to(ROOT))),release_qualified=False)
    data['active_400mhz_parent_antenna_review'].update(observed_utc=now,latest_candidate=candidate,
        latest_native_antenna='build/timing400/release_001/parent_dco_antenna_native_filled_011/native_completion.json',
        latest_conservative_geometry='build/timing400/release_001/parent_dco_antenna_geometry_filled_011/antenna/assessment.json',
        native_and_independent_antenna_checks_passed=True,antenna_qualified=False,release_qualified=False)
    data['active_400mhz_fill_capacitance_extraction']=electrical
    for key in ['release_qualified','selected','timing_closure_complete']:data[key]=False
    write(overview,data)
    print('Recorded progress032: exact final filled geometry passes all checked methods; corrected cap extraction live and electrical/release gates open.')

if __name__=='__main__':main()
