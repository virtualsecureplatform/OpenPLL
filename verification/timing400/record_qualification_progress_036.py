#!/usr/bin/env python3
"""Record terminal expanded capacitance extraction and exact device checks."""
from datetime import datetime, timezone
from pathlib import Path
import time
from record_qualification_progress_031 import ROOT, BASE, read, digest, write


def main():
    names = ['qualification_progress_035.json',
        'parent_filled_poly_metal_capacitance_extract_003/native_completion.json',
        'poly_metal_capacitance_collection_001/assessment.json',
        'flat_decap_warning_gate_inventory_001/assessment.json',
        'flat_poly_metal_decap_feedback_001/assessment.json',
        'parent_filled_poly_metal_capacitance_network_audit_001/assessment.json',
        'parent_filled_poly_metal_capacitance_positive_001/assessment.json',
        'poly_metal_capacitance_comparison_001/assessment.json',
        'current_poly_metal_digital_wire_capacitance_inventory_001/assessment.json']
    paths = [BASE/n for n in names] + [Path(__file__).resolve(),
        ROOT/'verification/release_requirements_400mhz.json',ROOT/'verification/release_plan_400mhz.json']
    prior,native,collection,inventory,feedback,network,positive,comparison,digital = [read(p) for p in paths[:len(names)]]
    assert native['native_extraction_completed'] and collection['source_collected']
    assert feedback['full_flat_terminal_warning_classification_passed']
    assert network['component_record_counts']['C']==49357430 and not network['missing_parent_nodes']
    assert network['component_record_counts'].get('negative_capacitors',0)==0
    assert positive['retained_positive_capacitors']==22512429 and positive['removed_exact_zero_capacitors']==26845001
    assert comparison['all_native_device_statements_preserved'] and comparison['new_native_device_statements']==100462
    assert digital['digital_nodes']==7468 and not digital['reported_sums_are_effective_loads']
    assert digest(paths[-2])=='02911569a2538d8b4d6c3139decdf7ec4d7c33bf2cbad85eed442947c0022b52'
    assert digest(paths[-1])=='2d6d5ed4404df842d64d42d68ebe593e4f627e65b4f90aaa48bef5f991e94b02'
    analog = []
    now_boot = time.clock_gettime(time.CLOCK_BOOTTIME)
    for proc in Path('/proc').glob('[0-9]*'):
        try:
            if (proc/'comm').read_text().strip()!='Xyce':
                continue
            if (proc/'stat').read_text().rsplit(')',1)[1].split()[0]=='Z':
                continue
            argv=[s.decode() for s in (proc/'cmdline').read_bytes().split(b'\0') if s]
            case=Path(argv[-1]).parent
            owner=read(case/'owner.json')
            deadline=owner.get('absolute_deadline_uptime',owner.get('deadline_uptime'))
            assert deadline>now_boot
            row=dict(pid=int(proc.name),argv=argv,owner=owner,remaining_budget_s=deadline-now_boot)
            waves=list(case.glob('*.prn'))
            if len(waves)==1:
                with waves[0].open('rb') as wave:
                    wave.seek(max(0,waves[0].stat().st_size-4096))
                    lines=wave.read().split(b'\n')[:-1]
                complete=[line.split() for line in lines if len(line.split())>=3 and line.split()[0].isdigit()]
                if complete:
                    row['latest_complete_wave_row_time_ns']=float(complete[-1][1])*1e9
                    row['waveform_observation_only']=True
            analog.append(row)
        except (FileNotFoundError,ProcessLookupError):
            continue
    assert len(analog)<=4
    now=datetime.now(timezone.utc).isoformat()
    cap=dict(directory='build/timing400/release_001/parent_filled_poly_metal_capacitance_extract_003',
        native_extraction_completed=True,raw_capacitors=49357430,positive_capacitors=22512429,
        exactly_zero_capacitors_removed=26845001,negative_capacitors=0,parent_nodes=359,
        active_device_nodes=network['active_device_nodes'],all_native_device_statements_preserved=100462,
        full_flattened_feedback_entries=2288,exact_decap_gate_warning_matches=2288,
        correct_rail_and_native_moscap_geometry_matches=2288,unclassified_feedback_entries=0,
        wrong_rail_box_and_missing_device_controls_rejected=True,floating_branches_preserved=True,
        digital_targets=7468,original_mapping_reused_with_device_and_conductor_identity_checks=True,
        driver_types_above_old_wire_diagonal_fixture_maximum=digital['types_with_wire_diagonal_above_fixture_maximum'],
        replacement_network_not_additive_patch=True,reported_sums_are_effective_loads=False,
        nonlinear_device_charge_included=False,fom_substrate_material_coverage_qualified=False,
        capacitance_distributed_on_wire_resistance_nodes=False,process_rc_enclosure_qualified=False,
        full_electrical_model_qualified=False,model_adopted=False)
    progress=dict(observed_utc=now,classification='expanded_network_device_and_warning_validation_progress_not_release',
        evidence_sha256={str(p.relative_to(ROOT)):digest(p) for p in paths},latest_candidate=prior['latest_candidate'],
        current_parent_wire_rc=prior['current_parent_wire_rc'],expanded_capacitance=cap,
        native_analog_jobs=sorted(analog,key=lambda r:r['pid']),native_analog_count=len(analog),
        native_analog_jobs_added=0,original_absolute_deadlines_retained=True,
        required_nominal_15pvt_scope_unchanged=True,physical_whole_pll_cases_passed=0,
        physical_ordered_mode_change_cases_passed=0,release_qualified=False,adopted=False,
        next_actions=['Resolve FOM/bulk electrical surface interpretation with explicit reference controls and supported enclosure',
            'Distribute validated fill-aware capacitance onto current wire resistance nodes without double counting',
            'Collect coarse14 TT100 endpoints and corrected duration probes before new oscillator dispatch',
            'Complete qualified nominal15PVT timing/calibration/interfaces,60 wholePLL cases and ordered mode changes',
            'Complete supply/noise, physical power/jitter/area and documented integration release gates'])
    snapshot=BASE/'qualification_progress_036.json'
    assert not snapshot.exists()
    write(snapshot,progress)
    overview=ROOT/'build/timing450/implementation_assessment.json'
    data=read(overview)
    data['latest_400mhz_qualification_progress']=str(snapshot.relative_to(ROOT))
    data['active_400mhz_fill_capacitance_extraction']=cap
    data['active_400mhz_poly_metal_fill_capacitance_extraction']=cap
    for name in ['release_qualified','selected','timing_closure_complete']:
        data[name]=False
    write(overview,data)
    print('Progress036: expanded network collected; all100462 native devices unchanged,2288 warnings classified,22512429 positive capacitors retained; qualification remains open.')


if __name__=='__main__':
    main()
