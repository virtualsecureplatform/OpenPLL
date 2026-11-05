#!/usr/bin/env python3
"""Record current three-corner parent wire RC and full-GDS correspondence."""
from datetime import datetime, timezone
from pathlib import Path
import time
from record_qualification_progress_031 import ROOT, BASE, read, digest, write


def main():
    evidence = ['qualification_progress_034.json','current_parent_wire_rc_001/native_completion.json',
        'current_parent_wire_rc_audit_001/assessment.json','current_parent_wire_rc_geometry_001/assessment.json',
        'parent_filled_poly_metal_capacitance_extract_003/owner.json',
        'parent_filled_poly_metal_capacitance_extract_003/input_manifest.json']
    paths = [BASE/n for n in evidence] + [Path(__file__).resolve(),
        ROOT/'verification/release_requirements_400mhz.json', ROOT/'verification/release_plan_400mhz.json']
    prior = read(paths[0])
    wire = read(paths[2])
    geometry = read(paths[3])
    assert wire['all_def_terminals_matched'] and wire['all_resistance_graphs_connected']
    assert not wire['terminal_path_corner_order_inversions']
    assert geometry['all_coordinates_correlated'] and geometry['coordinates_tested']==10636
    cap = BASE/'parent_filled_poly_metal_capacitance_extract_003'
    status = read(cap/'status.json')
    pid = status['native_pid']
    proc = Path('/proc')/str(pid)
    assert (proc/'stat').read_text().rsplit(')',1)[1].split()[0]!='Z'
    argv = (proc/'cmdline').read_bytes().replace(b'\0',b' ').decode()
    assert 'magicdnull' in argv
    analog = []
    boot = time.clock_gettime(time.CLOCK_BOOTTIME)
    for proc in Path('/proc').glob('[0-9]*'):
        try:
            if (proc/'comm').read_text().strip()!='Xyce':
                continue
            if (proc/'stat').read_text().rsplit(')',1)[1].split()[0]=='Z':
                continue
            args = [x.decode() for x in (proc/'cmdline').read_bytes().split(b'\0') if x]
            owner = read(Path(args[-1]).parent/'owner.json')
            deadline = owner.get('absolute_deadline_uptime',owner.get('deadline_uptime'))
            assert deadline > boot
            analog.append(dict(pid=int(proc.name),argv=args,owner=owner,remaining_budget_s=deadline-boot))
        except (FileNotFoundError,ProcessLookupError):
            continue
    assert len(analog)<=4
    now = datetime.now(timezone.utc).isoformat()
    rc = dict(directory='build/timing400/release_001/current_parent_wire_rc_001',
        rc_corners=['min','nom','max'],signal_nets_each_corner=357,all_def_terminals_matched=True,
        all_resistors_positive=True,all_graphs_connected=True,tree_graphs_each_corner=357,
        terminal_path_corner_order_inversions=0,full_gds_coordinate_observations=10636,
        unmatched_coordinate_observations=0,wrong_terminal_and_net_controls_rejected=True,
        expected_net_membership_only=True,unique_conductor_layer_identity_qualified=False,
        default_small_coupling_grounding_threshold_ff=0.1,pin_capacitance_included=False,
        macro_internal_rc_included=False,generated_gds_fill_included=False,
        full_gds_capacitance_distributed_on_resistance_nodes=False,
        full_rc_enclosure_qualified=False,physical_timing_qualified=False,model_adopted=False)
    progress = dict(observed_utc=now,classification='three_corner_parent_wire_rc_and_geometry_progress_not_release',
        evidence_sha256={str(p.relative_to(ROOT)):digest(p) for p in paths},latest_candidate=prior['latest_candidate'],
        current_parent_wire_rc=rc,poly_metal_capacitance_extraction=dict(native_pid=pid,native_argv=argv,
            status_at_observation=status,raw_network_terminal=False,full_feedback_capture_requested=True),
        native_analog_jobs=sorted(analog,key=lambda r:r['pid']),native_analog_count=len(analog),
        native_analog_jobs_added=0,original_absolute_deadlines_retained=True,
        required_nominal_15pvt_scope_unchanged=True,physical_whole_pll_cases_passed=0,
        physical_ordered_mode_change_cases_passed=0,release_qualified=False,adopted=False,
        next_actions=['Collect expanded poly+metal capacitor extraction, inspect full feedback and compare intrinsic devices to current geometry',
            'Resolve remaining FOM/substrate material and distribute validated capacitance onto matching resistance nodes without double counting',
            'Collect adjacent TT100 coarse14 endpoints and both corrected duration probes before new oscillator dispatch',
            'Complete qualified nominal15PVT timing/calibration/interfaces,60 wholePLL cases and ordered mode changes',
            'Complete supply/noise, physical power/jitter/area and documented integration release gates'])
    snapshot = BASE/'qualification_progress_035.json'
    assert not snapshot.exists()
    write(snapshot,progress)
    overview = ROOT/'build/timing450/implementation_assessment.json'
    data = read(overview)
    data['latest_400mhz_qualification_progress']=str(snapshot.relative_to(ROOT))
    data['active_400mhz_parent_wire_rc']=rc
    for name in ['release_qualified','selected','timing_closure_complete']:
        data[name]=False
    write(overview,data)
    print('Progress035: current parent three-corner wire RC and10636 GDS coordinates verified; fill-aware distributed loading and full qualification remain open.')


if __name__=='__main__':
    main()
