#!/usr/bin/env python3
"""Record stock symbolic fill evidence and isolated serial build progress."""
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
    proof_path = base / 'DCO_stock_symbolic_pattern_comparison_002/assessment.json'
    proof = json.loads(proof_path.read_text())
    assert proof['stock_KLU_symbolic_pattern_comparison_completed']
    assert not proof['nonlinear_device_and_MNA_patterns_included']
    for filename, value in {**proof['input_sha256'], **proof['artifacts']}.items():
        assert digest(Path(filename)) == value, filename
    live, builders = [], []
    for directory in Path('/proc').glob('[0-9]*'):
        row = process(int(directory.name))
        if not row['live']:
            continue
        if row['argv'][0] == '/opt/xyce/bin/Xyce':
            live.append(row)
        if len(row['argv']) > 1 and row['argv'][1] == 'verification/timing400/build_stock_serial_Xyce.py':
            builders.append(row)
    assert len(live) <= 4 and len(builders) == 1
    build = base / 'stock_serial_Xyce_001'
    build_status = build / 'status.json'
    observed = json.loads(build_status.read_text()) if build_status.exists() else dict(
        state='preparing_pinned_build_inputs', observed_live_runner=builders[0])
    paths = [Path(__file__).resolve(), owner, base / 'qualification_progress_071.json', proof_path,
             Path(__file__).with_name('build_stock_serial_Xyce.py')]
    previous = json.loads((base / 'qualification_progress_071.json').read_text())
    work = dict(passive_block_symbolic_patterns=proof['results'],
        nonlinear_device_and_MNA_patterns_included=False,
        native_full_runtime_prediction_qualified=False,
        exact_grounding_did_not_reduce_passive_block_AMD_estimated_flops=True,
        source_engine_or_library_modified=False,
        stock_serial_build_directory=str(build.relative_to(root)),
        stock_serial_build_runner=builders[0], stock_serial_build_status=observed,
        installed_golden_simulator_unchanged=True, native_circuit_or_solver_changed=False,
        serial_factor_reuse_controls_passed=False, serial_binary_adopted=False,
        original_deadline_uptime=deadline, budget_restarted=False,
        release_qualified=False, adopted=False)
    throughput = previous['throughput_followup']
    throughput['stock_symbolic_fill_and_serial_build'] = work
    followup = previous['restored_self_C_operator_followup']
    followup.update(current_native_engines=live, throughput_followup=throughput)
    cases = {}
    for name in ['DCO_domain_nom_tt27_c0_f247_80ns_canonical_ground_001',
                 'DCO_native_zero_wire_R_nom_tt27_c0_f247_80ns_001']:
        folder = base / name
        status = json.loads((folder / 'status.json').read_text())
        native = process(status['native_pid'])
        assert native['live'] and native['argv'][-1] == str((folder / 'point.cir').resolve())
        wave = folder / 'point.cir.prn'
        rows = [line.split() for line in wave.read_text().splitlines()[1:]
                if len(line.split()) == 4 and line.split()[0].isdigit()] if wave.exists() else []
        cases[name] = dict(status=status, native=native, samples_observed=len(rows),
            last_observed_simulation_time_s=float(rows[-1][1]) if rows else None,
            waveform_observation_is_partial=True)
    throughput['active_native_transients'] = cases
    followup.update(native_points=cases, active_check_statuses=cases)
    previous.update(observed_utc=datetime.now(timezone.utc).isoformat(),
        classification='stock_passive_block_symbolic_fill_analysis_completed_isolated_unmodified_serial_build_live_controls_pending',
        throughput_followup=throughput, restored_self_C_operator_followup=followup,
        evidence_sha256={str(path.relative_to(root)): digest(path) for path in paths},
        native_analog_jobs=live, native_analog_count=len(live),
        current_native_CAD_and_analog_engines=live, release_qualified=False, adopted=False,
        physical_whole_pll_passes=0)
    snapshot = base / 'qualification_progress_072.json'
    assert not snapshot.exists()
    save(snapshot, previous)
    overview = root / 'build/timing450/implementation_assessment.json'
    state = json.loads(overview.read_text())
    state.update(latest_400mhz_qualification_progress=str(snapshot.relative_to(root)),
        active_400mhz_restored_self_C_operator_followup=followup,
        active_400mhz_throughput_followup=throughput,
        release_qualified=False, selected=False, timing_closure_complete=False)
    save(overview, state)
    print('Progress072: stock symbolic analysis completed; isolated serial build live, equivalence/reuse controls pending.')


if __name__ == '__main__':
    main()
