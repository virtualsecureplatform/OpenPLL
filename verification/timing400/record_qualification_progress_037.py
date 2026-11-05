#!/usr/bin/env python3
"""Record installed capacitance-corner controls and live FOM sensitivity check."""
from datetime import datetime, timezone
from pathlib import Path
import time
from record_qualification_progress_031 import ROOT, BASE, read, digest, write


def main():
    names=['qualification_progress_036.json','capacitance_corner_controls_001/assessment.json',
        'capacitance_corner_control_audit_001/assessment.json','fom_bulk_surface_reference_view_004/assessment.json',
        'fom_bulk_surface_reference_extract_004/owner.json','fom_bulk_surface_reference_extract_004/input_manifest.json',
        'fom_bulk_surface_reference_collection_001/owner.json','fom_bulk_surface_reference_collection_001/input_manifest.json']
    paths=[BASE/n for n in names]+[Path(__file__).resolve(),ROOT/'verification/release_requirements_400mhz.json',
        ROOT/'verification/release_plan_400mhz.json']
    prior,controls,audit,view,owner,manifest,collector_owner,collector_manifest=[read(p) for p in paths[:len(names)]]
    assert controls['native_cad_controls_completed']==18
    assert audit['all_five_control_effective_capacitances_strictly_ordered']
    assert audit['native_nand_mos_device_statements_preserved_after_schema_normalization']==8
    assert audit['exported_nand_geometry_and_terminal_parameters_preserved_across_m_and_x_cards']==8
    assert view['fom_ideal_bulk_reference_only'] and view['manufacturing_gds_unchanged']
    assert not view['reference_ohmic_surfaces_are_manufacturing_masks']
    assert owner['deadline_uptime']==collector_owner['deadline_uptime']==read(BASE/'candidate_layout_checks_001/owner.json')['deadline_uptime']
    status=read(BASE/'fom_bulk_surface_reference_extract_004/status.json')
    native_pid=status['native_pid']
    proc=Path('/proc')/str(native_pid)
    assert (proc/'stat').read_text().rsplit(')',1)[1].split()[0]!='Z'
    native_argv=(proc/'cmdline').read_bytes().replace(b'\0',b' ').decode()
    assert 'magicdnull' in native_argv
    collector_pid=collector_owner['runner_pid']
    collector_proc=Path('/proc')/str(collector_pid)
    assert (collector_proc/'stat').read_text().rsplit(')',1)[1].split()[0]!='Z'
    assert 'collect_fom_bulk_surface_reference.py' in (collector_proc/'cmdline').read_bytes().decode()
    analog=[]
    boot=time.clock_gettime(time.CLOCK_BOOTTIME)
    for proc in Path('/proc').glob('[0-9]*'):
        try:
            if (proc/'comm').read_text().strip()!='Xyce' or (proc/'stat').read_text().rsplit(')',1)[1].split()[0]=='Z':
                continue
            argv=[v.decode() for v in (proc/'cmdline').read_bytes().split(b'\0') if v]
            case_owner=read(Path(argv[-1]).parent/'owner.json')
            deadline=case_owner.get('absolute_deadline_uptime',case_owner.get('deadline_uptime'))
            assert deadline>boot
            analog.append(dict(pid=int(proc.name),argv=argv,owner=case_owner,remaining_budget_s=deadline-boot))
        except (FileNotFoundError,ProcessLookupError):
            continue
    assert len(analog)<=4
    now=datetime.now(timezone.utc).isoformat()
    reference=dict(view='build/timing400/release_001/fom_bulk_surface_reference_view_004',
        extraction='build/timing400/release_001/fom_bulk_surface_reference_extract_004',
        collector='build/timing400/release_001/fom_bulk_surface_reference_collection_001',
        native_pid=native_pid,native_argv=native_argv,collector_pid=collector_pid,status_at_observation=status,
        counterfactual_ideal_bulk_surface_only=True,reference_surface_area_um2=view['reference_fom_footprint_area_um2'],
        pwell_surface_area_um2=view['pwell_reference_surface_area_um2'],nwell_surface_area_um2=view['nwell_reference_surface_area_um2'],
        manufacturing_gds_unchanged=True,original_gate_and_contact_geometry_preserved=True,
        finite_bulk_impedance_included=False,manufacturing_material_equivalence_qualified=False,
        quantitative_upper_or_lower_enclosure_qualified=False,model_adopted=False,
        owner=owner,collector_owner=collector_owner)
    corner=dict(isolated_native_cad_checks=18,rc_corners=['min','nom','max'],
        effective_capacitance_controls_strictly_ordered=5,actual_nand_mos_devices_preserved=8,
        m_to_foundry_wrapper_x_terminal_parameters_preserved=True,
        missing_device_and_reversed_order_controls_rejected=True,
        isolated_bulk_and_supply_references_assumed_ideal=True,
        full_layout_capacitance_corner_extractions_completed=False,physical_timing_qualified=False)
    progress=dict(observed_utc=now,classification='capacitance_corner_controls_and_live_fom_reference_progress_not_release',
        evidence_sha256={str(p.relative_to(ROOT)):digest(p) for p in paths},latest_candidate=prior['latest_candidate'],
        expanded_capacitance=prior['expanded_capacitance'],current_parent_wire_rc=prior['current_parent_wire_rc'],
        capacitance_corner_controls=corner,fom_bulk_surface_reference=reference,
        native_analog_jobs=sorted(analog,key=lambda r:r['pid']),native_analog_count=len(analog),native_analog_jobs_added=0,
        original_absolute_deadlines_retained=True,required_nominal_15pvt_scope_unchanged=True,
        physical_whole_pll_cases_passed=0,physical_ordered_mode_change_cases_passed=0,release_qualified=False,adopted=False,
        next_actions=['Collect FOM reference warning/network/device/sensitivity assessments under the original cutoff; retain counterfactual scope',
            'Complete full-layout C corners using validated M/X schemas; preserve floating nodes and avoid double counting',
            'Resolve supported material/RC enclosure and distribute C onto matching R nodes before model adoption',
            'Collect coarse14 TT100 endpoints and corrected duration probes before new oscillator dispatch',
            'Complete qualified nominal15PVT timing/calibration/interfaces,60 wholePLL cases and ordered mode changes',
            'Complete supply/noise, physical power/jitter/area and documented integration release gates'])
    snapshot=BASE/'qualification_progress_037.json'
    assert not snapshot.exists()
    write(snapshot,progress)
    overview=ROOT/'build/timing450/implementation_assessment.json'
    data=read(overview)
    data['latest_400mhz_qualification_progress']=str(snapshot.relative_to(ROOT))
    data['active_400mhz_fom_bulk_surface_reference']=reference
    data['active_400mhz_capacitance_corner_controls']=corner
    for name in ['release_qualified','selected','timing_closure_complete']:
        data[name]=False
    write(overview,data)
    print('Progress037:18 corner controls pass independent audit; bounded FOM reference/collector live; four analog jobs and release scope unchanged.')


if __name__=='__main__':
    main()
