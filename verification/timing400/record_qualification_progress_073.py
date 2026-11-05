#!/usr/bin/env python3
"""Record first full-R timestep, serial dependency success and throughput guard."""
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
    previous_path = base / 'qualification_progress_072.json'
    previous = json.loads(previous_path.read_text())
    build = base / 'stock_serial_Xyce_001'
    receipts = json.loads((build / 'stage_receipts.json').read_text())
    assert all(row['exit_code'] == 0 for row in receipts[:3]) and len(receipts) >= 3
    paths = [Path(__file__).resolve(), owner, previous_path, build / 'input_manifest.json']
    queued = {}
    for name in ['stock_serial_factor_reuse_controls_001',
                 'DCO_domain_nom_tt27_c0_f247_80ns_stock_serial_corrected_002', 'stock_serial_Xyce_001']:
        folder = base / name
        status = json.loads((folder / 'status.json').read_text())
        handle = process(status['runner_pid'])
        assert handle['live']
        queued[name] = dict(status=status, runner=handle)
        paths.append(folder / 'owner.json')
    pending = base / 'DCO_domain_nom_tt27_c0_f247_80ns_stock_serial_corrected_002'
    preparation = json.loads((pending / 'preparation_manifest.json').read_text())
    assert preparation['minimum_throughput_observation_s'] == 120
    assert preparation['preserve_if_projected_finish_within_twice_remaining_budget']
    for name, value in preparation['input_sha256'].items():
        assert digest(Path(name)) == value, name
    superseded = base / 'DCO_domain_nom_tt27_c0_f247_80ns_stock_serial_corrected_001/superseded_for_bounded_throughput_guard.json'
    old = json.loads(superseded.read_text())
    assert not process(old['pid'])['live'] and not old['native_simulation_interrupted']
    paths.extend([pending / 'preparation_manifest.json', superseded,
                  Path(__file__).with_name('run_DCO_stock_serial_corrected_point_v2.py'),
                  Path(__file__).with_name('check_stock_serial_factor_reuse.py')])
    cases, live = {}, []
    for name in ['DCO_domain_nom_tt27_c0_f247_80ns_canonical_ground_001',
                 'DCO_native_zero_wire_R_nom_tt27_c0_f247_80ns_001']:
        folder = base / name
        status = json.loads((folder / 'status.json').read_text())
        native = process(status['native_pid'])
        assert native['live'] and native['argv'][-1] == str((folder / 'point.cir').resolve())
        live.append(native)
        text = (folder / 'point.cir.prn').read_text()
        lines = text.splitlines()
        if not text.endswith('\n'): lines.pop()
        rows = [line.split() for line in lines[1:] if len(line.split()) == 4 and line.split()[0].isdigit()]
        cases[name] = dict(status=status, native=native, samples_observed=len(rows),
            last_observed_simulation_time_s=float(rows[-1][1]) if rows else None,
            waveform_observation_is_partial=True)
    work = previous['throughput_followup']
    serial = work['stock_symbolic_fill_and_serial_build']
    serial.update(stock_serial_dependency_configuration_build_and_install_passed=True,
        successful_build_stages_observed=receipts, live_pipeline=queued,
        bounded_throughput_guard_replaces_any_positive_sample_guard=True,
        partial_native_waveform_preserved=True, original_deadline_uptime=deadline,
        full_DCO_performance_improvement_demonstrated=False)
    work.update(active_native_transients=cases, stock_symbolic_fill_and_serial_build=serial)
    followup = previous['restored_self_C_operator_followup']
    followup.update(current_native_engines=live, native_points=cases, active_check_statuses=cases,
                    throughput_followup=work)
    previous.update(observed_utc=datetime.now(timezone.utc).isoformat(),
        classification='full_R_first_positive_timestep_observed_stock_serial_dependency_build_install_pass_handoff_requires_controls_and_bounded_throughput',
        throughput_followup=work, restored_self_C_operator_followup=followup,
        evidence_sha256={str(path.relative_to(root)): digest(path) for path in paths},
        native_analog_jobs=live, native_analog_count=len(live),
        current_native_CAD_and_analog_engines=live,
        release_qualified=False, adopted=False, physical_whole_pll_passes=0)
    snapshot = base / 'qualification_progress_073.json'
    assert not snapshot.exists()
    save(snapshot, previous)
    overview = root / 'build/timing450/implementation_assessment.json'
    state = json.loads(overview.read_text())
    state.update(latest_400mhz_qualification_progress=str(snapshot.relative_to(root)),
        active_400mhz_restored_self_C_operator_followup=followup,
        active_400mhz_throughput_followup=work,
        release_qualified=False, selected=False, timing_closure_complete=False)
    save(overview, state)
    print('Progress073: first full-R timestep observed; serial dependencies built/installed; controlled throughput handoff queued.')


if __name__ == '__main__':
    main()
