#!/usr/bin/env python3
"""Record FOM sensitivity, full-C corner execution and missing diode scope work."""
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
import time
from check_bbpd_repair_identity import design
from record_qualification_progress_031 import ROOT,BASE,read,digest,write


def main():
    names=['qualification_progress_037.json',
        'fom_bulk_surface_reference_extract_004/native_completion.json',
        'fom_bulk_surface_reference_collection_001/assessment.json',
        'fom_bulk_surface_decap_feedback_001/assessment.json',
        'fom_bulk_surface_reference_network_audit_001/assessment.json',
        'fom_bulk_surface_reference_comparison_001/assessment.json',
        'primitive_corner_exports_001/assessment.json','primitive_corner_export_audit_001/assessment.json',
        'current_diode_geometry_inventory_001/assessment.json',
        'hs_diode_geometry_comparison_001/plan.json','hs_diode_geometry_comparison_001/owner.json',
        'hs_diode_geometry_comparison_001/run_owner.json','hs_diode_geometry_comparison_001/run_input_manifest.json',
        'poly_metal_full_capacitance_corners_001/superseded.json',
        'poly_metal_full_capacitance_corners_002/owner.json','poly_metal_full_capacitance_corners_002/input_manifest.json']
    paths=[BASE/n for n in names]+[Path(__file__).resolve(),ROOT/'verification/release_requirements_400mhz.json',
        ROOT/'verification/release_plan_400mhz.json']
    prior=read(paths[0]);fom_network=read(paths[4]);fom_comparison=read(paths[5]);diodes=read(paths[8])
    assert read(paths[2])['source_collected'] and read(paths[3])['full_flat_terminal_warning_classification_passed']
    assert fom_comparison['all_native_device_statements_preserved']
    assert fom_network['component_record_counts']['C']==49727566
    assert fom_network['component_record_counts'].get('negative_capacitors',0)==0 and not fom_network['missing_parent_nodes']
    assert read(paths[7])['exported_device_geometry_and_terminal_order_preserved']
    assert diodes['hs_instances_outside_existing_geometry_scope']==724 and diodes['hd_instances_in_existing_geometry_scope']==2
    def_paths=[BASE/'parent_dco_antenna_targeted_011/route.def',BASE/'compact_internal_antenna_001/route.def',
        BASE/'bbpd_internal_antenna_001/route.def',ROOT/'openlane/IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160/runs/c1fine_range_001/final/def/IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160.def']
    masters=Counter()
    for path in def_paths:
        cells,_,_=design(path)
        masters.update(m for m,_ in cells.values())
    assert masters['sky130_fd_sc_hs__diode_2']==724 and masters['sky130_fd_sc_hd__diode_2']==2
    paths+=def_paths
    hs_owner=read(BASE/'hs_diode_geometry_comparison_001/run_owner.json')
    hs_pid=hs_owner['runner_pid'];hp=Path('/proc')/str(hs_pid)
    assert (hp/'stat').read_text().rsplit(')',1)[1].split()[0]!='Z'
    assert 'run_hs_diode_comparison.py' in (hp/'cmdline').read_bytes().decode()
    hs_status=read(BASE/'hs_diode_geometry_comparison_001/status.json')
    queue=BASE/'poly_metal_full_capacitance_corners_002'
    q_owner=read(queue/'owner.json');qp=Path('/proc')/str(q_owner['runner_pid'])
    assert (qp/'stat').read_text().rsplit(')',1)[1].split()[0]!='Z'
    q_status=read(queue/'status.json')
    corner=q_status['corner'];native_status=read(queue/corner/'status.json');native_pid=native_status['native_pid']
    np=Path('/proc')/str(native_pid)
    assert (np/'stat').read_text().rsplit(')',1)[1].split()[0]!='Z'
    assert 'magicdnull' in (np/'cmdline').read_bytes().decode()
    analog=[];boot=time.clock_gettime(time.CLOCK_BOOTTIME)
    for p in Path('/proc').glob('[0-9]*'):
        try:
            if (p/'comm').read_text().strip()!='Xyce' or (p/'stat').read_text().rsplit(')',1)[1].split()[0]=='Z':continue
            argv=[x.decode() for x in (p/'cmdline').read_bytes().split(b'\0') if x]
            owner=read(Path(argv[-1]).parent/'owner.json')
            deadline=owner.get('absolute_deadline_uptime',owner.get('deadline_uptime'));assert deadline>boot
            analog.append(dict(pid=int(p.name),argv=argv,owner=owner,remaining_budget_s=deadline-boot))
        except (FileNotFoundError,ProcessLookupError):continue
    assert len(analog)<=4
    fom=dict(native_extraction_completed=True,raw_capacitor_records=49727566,exact_zero_records=26920418,
        positive_capacitors=22807148,negative_capacitors=0,parent_nodes=359,classified_decap_warnings=2288,
        all100462_native_device_statements_preserved=True,counterfactual_reference_only=True,
        three_critical_parent_diagonal_change_range_percent=[.45750498979374365,.7360179959107929],
        changes_are_effective_timing_loads=False,actual_fom_material_equivalence_qualified=False,
        quantitative_material_enclosure_qualified=False,model_adopted=False)
    diode=dict(actual_instances=726,actual_hs_diode2_instances=724,actual_hd_diode2_instances=2,
        native_and_placed_instance_counts_agree=True,existing_translator_correctly_rejects_hs_geometry=True,
        hs_effective_area_um2='.6417',hs_effective_perimeter_um='3.24',hs_native_analyses_prepared=360,
        fresh_electrical_pvt_cases=15,fresh_noise_bias_cases=75,runner_pid=hs_pid,owner=hs_owner,status_at_observation=hs_status,
        golden_simulator='upstream Xyce',independent_reference='ngspice47',own_native_concurrency=1,
        admission_lock_held_through_each_native_exit=True,hs_geometry_comparison_passed=False,
        all_current_diode_geometries_qualified=False,model_adopted=False)
    full_c=dict(queue=str(queue.relative_to(ROOT)),owner=q_owner,status_at_observation=q_status,
        current_corner=corner,verified_native_pid=native_pid,min_max_sequential=True,
        old_queue_superseded_before_any_corner_native_launch=True,parent_cleanup_grace_s=15,
        native_absolute_cutoff_unchanged=True,full_corner_assessments_pending=True,full_rc_enclosure_qualified=False)
    progress=dict(observed_utc=datetime.now(timezone.utc).isoformat(),classification='fom_sensitivity_and_missing_geometry_scope_progress_not_release',
        evidence_sha256={str(p.relative_to(ROOT)):digest(p) for p in paths},latest_candidate=prior['latest_candidate'],
        expanded_capacitance=prior['expanded_capacitance'],current_parent_wire_rc=prior['current_parent_wire_rc'],
        fom_reference=fom,current_diode_geometry_work=diode,full_capacitance_corners=full_c,
        native_analog_jobs=sorted(analog,key=lambda r:r['pid']),native_analog_count=len(analog),
        original_absolute_deadlines_retained=True,required_nominal_15pvt_scope_unchanged=True,
        physical_whole_pll_cases_passed=0,physical_ordered_mode_change_cases_passed=0,release_qualified=False,adopted=False,
        next_actions=['Collect full-layout C corners and assess wrapper device/node identity, feedback and positive networks before model adoption',
            'Finish the queued observed-HS-geometry DC/AC/charge/noise comparison; retain legacy fixed-geometry guard',
            'Resolve supported material/RC enclosure and distribute C onto matching R nodes without double counting',
            'Collect coarse14 TT100 endpoints and corrected duration probes before new oscillator dispatch',
            'Complete qualified nominal15PVT timing/calibration/interfaces,60 wholePLL cases and ordered mode changes',
            'Complete supply/noise, physical power/jitter/area and documented integration release gates'])
    snapshot=BASE/'qualification_progress_038.json';assert not snapshot.exists();write(snapshot,progress)
    overview=ROOT/'build/timing450/implementation_assessment.json';data=read(overview)
    data['latest_400mhz_qualification_progress']=str(snapshot.relative_to(ROOT))
    data['active_400mhz_fom_bulk_surface_reference']=fom
    data['active_400mhz_full_capacitance_corners']=full_c
    data['active_400mhz_current_diode_geometry_work']=diode
    for key in ['release_qualified','selected','timing_closure_complete']:data[key]=False
    write(overview,data)
    print('Progress038: FOM sensitivity assessed,724 HS diodes identified outside prior scope, bounded HS comparison queued, full-C corners executing; release remains open.')


if __name__=='__main__':main()
