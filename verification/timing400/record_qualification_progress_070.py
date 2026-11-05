#!/usr/bin/env python3
"""Record independently audited exact ground substitution and actual live jobs."""
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from compile_local_C_operators_v2 import digest, save
from record_qualification_progress_045 import process


def main():
    root = Path(__file__).resolve().parents[2]
    base = root / 'build/timing400/release_001'
    owner = base / 'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    paths = [Path(__file__).resolve(), owner, base / 'qualification_progress_069.json']
    def proof(name):
        path = base / name / 'assessment.json'
        data = json.loads(path.read_text())
        for filename, value in {**data.get('input_sha256', {}), **data.get('artifacts', {})}.items():
            assert digest(Path(filename)) == value, filename
        paths.append(path)
        return data
    controls = proof('zero_voltage_canonicalization_controls_001')
    audit = proof('DCO_ground_coordinate_mapping_checks_001')
    assert controls['native_voltage_constraint_canonicalization_controls_passed']
    assert audit['independent_full_boundary_and_initial_charge_mapping_passed']
    old = base / 'DCO_domain_nom_tt27_c0_f247_80ns_savedIC_001'
    stopped = old / 'stopped_for_exact_ground_coordinate_change.json'
    receipt = json.loads(stopped.read_text())
    assert not process(receipt['pid'])['live']
    assert receipt['deadline_uptime'] == deadline and not receipt['physical_approximation']
    paths.append(stopped)
    live = []
    for directory in Path('/proc').glob('[0-9]*'):
        try:
            if (directory / 'comm').read_text().strip() in ['Xyce', 'ngspice', 'magicdnull']:
                row = process(int(directory.name))
                if row['live']:
                    live.append(row)
        except (FileNotFoundError, ProcessLookupError):
            continue
    assert len(live) <= 4
    cases = {}
    for name in ['DCO_domain_nom_tt27_c0_f247_80ns_canonical_ground_001',
                 'DCO_native_zero_wire_R_nom_tt27_c0_f247_80ns_001']:
        folder = base / name
        status = json.loads((folder / 'status.json').read_text())
        native = process(status['native_pid'])
        assert native['live'] and native['argv'][0] == '/opt/xyce/bin/Xyce'
        assert native['argv'][-1] == str((folder / 'point.cir').resolve())
        wave = folder / 'point.cir.prn'
        rows = []
        if wave.exists():
            for line in wave.read_text().splitlines()[1:]:
                fields = line.split()
                if len(fields) == 4 and fields[0].isdigit():
                    rows.append(fields)
        cases[name] = dict(status=status, native=native, samples_observed=len(rows),
            last_observed_simulation_time_s=float(rows[-1][1]) if rows else None,
            waveform_observation_is_partial=True)
        paths.append(folder / 'input_manifest.json')
    new_log = base / 'DCO_domain_nom_tt27_c0_f247_80ns_canonical_ground_001/native.log'
    assert 'Number of Unknowns = 174551' in new_log.read_text()
    for name, value in {
        'verification/release_requirements_400mhz.json': '02911569a2538d8b4d6c3139decdf7ec4d7c33bf2cbad85eed442947c0022b52',
        'verification/release_plan_400mhz.json': '2d6d5ed4404df842d64d42d68ebe593e4f627e65b4f90aaa48bef5f991e94b02'}.items():
        assert digest(root / name) == value
        paths.append(root / name)
    change = dict(native_controls_passed=True, independent_full_boundary_mapping_passed=True,
        removed_external_zero_constraints=296, original_unknowns=175143,
        native_reported_unknowns=174551, physical_wire_nodes_eliminated=0,
        physical_macro_R_C_and_device_cards_byte_identical=True,
        all_retained_initial_voltages_exactly_preserved=True,
        maximum_control_voltage_difference_V=max(controls['maximum_voltage_differences_V']),
        maximum_control_current_difference_A=controls['maximum_supply_current_difference_A'],
        maximum_control_crossing_difference_s=controls['maximum_rising_crossing_difference_s'],
        physical_circuit_approximated=False, source_model_convention_unchanged=True,
        full_DCO_performance_improvement_demonstrated=False,
        prior_full_native_stop_receipt=str(stopped.relative_to(root)),
        original_deadline_uptime=deadline, budget_restarted=False,
        DCO_timing_or_frequency_qualified=False, release_qualified=False, adopted=False)
    previous = json.loads((base / 'qualification_progress_069.json').read_text())
    followup = previous['restored_self_C_operator_followup']
    throughput = previous['throughput_followup']
    throughput.update(active_native_transients=cases, exact_ground_coordinate_change=change)
    followup.update(current_native_engines=live, native_points=cases, active_check_statuses=cases,
                    throughput_followup=throughput)
    previous.update(observed_utc=datetime.now(timezone.utc).isoformat(),
        classification='exact_ground_substitution_native_controls_and_independent_full_boundary_audit_pass_full_R_and_ideal_wire_transients_live',
        exact_ground_coordinate_change=change, throughput_followup=throughput,
        restored_self_C_operator_followup=followup,
        evidence_sha256={str(path.relative_to(root)): digest(path) for path in paths},
        native_analog_jobs=live, native_analog_count=len(live),
        current_native_CAD_and_analog_engines=live,
        release_qualified=False, adopted=False, physical_whole_pll_passes=0,
        next_actions=[
            'Assess full-R exact-ground transient throughput and finish both existing native transients within the original deadline; partial or ideal-wire oscillation does not qualify release frequency',
            'Qualify substrate-return convention, spatial and dynamic errors and independent numerical convergence before adopting any physical runtime model',
            'Complete all frozen four-mode nominal1.8V/15PVT calibration, timing, reset/CDC, wholePLL, physical and reproducibility gates'])
    snapshot = base / 'qualification_progress_070.json'
    assert not snapshot.exists()
    save(snapshot, previous)
    overview = root / 'build/timing450/implementation_assessment.json'
    state = json.loads(overview.read_text())
    state.update(latest_400mhz_qualification_progress=str(snapshot.relative_to(root)),
        active_400mhz_restored_self_C_operator_followup=followup,
        active_400mhz_throughput_followup=throughput,
        release_qualified=False, selected=False, timing_closure_complete=False)
    state['active_400mhz_distributed_RC_check'].update(native_analog_jobs=len(live),
        state='exact_ground_coordinate_native_controls_and_full_boundary_audit_pass_native_transients_live')
    save(overview, state)
    print('Progress070: exact ground mapping independently checked; native transients live, release gates remain open.')


if __name__ == '__main__':
    main()
