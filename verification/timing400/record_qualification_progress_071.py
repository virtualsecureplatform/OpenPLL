#!/usr/bin/env python3
"""Record a corrected-C diagnostic prepared without another native launch."""
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from compile_local_C_operators_v2 import digest, save
from record_qualification_progress_045 import process


def main():
    root = Path(__file__).resolve().parents[2]
    base = root / 'build/timing400/release_001'
    previous_path = base / 'qualification_progress_070.json'
    previous = json.loads(previous_path.read_text())
    prepared = base / 'DCO_domain_nom_tt27_c0_f247_80ns_corrected_ground_prepared_001'
    assessment = prepared / 'assessment.json'
    proof = json.loads(assessment.read_text())
    for name, value in proof['input_sha256'].items():
        assert digest(Path(name)) == value, name
    assert proof['corrected_C_diagnostic_preparation_passed']
    assert proof['all_noncapacitive_macro_statements_identical']
    assert not proof['native_started'] and not proof['automatic_launch']
    deadline = proof['original_deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    live, cases = [], {}
    for name in ['DCO_domain_nom_tt27_c0_f247_80ns_canonical_ground_001',
                 'DCO_native_zero_wire_R_nom_tt27_c0_f247_80ns_001']:
        folder = base / name
        status = json.loads((folder / 'status.json').read_text())
        native = process(status['native_pid'])
        assert native['live'] and native['argv'][-1] == str((folder / 'point.cir').resolve())
        live.append(native)
        wave = folder / 'point.cir.prn'
        rows = [line.split() for line in wave.read_text().splitlines()[1:]
                if len(line.split()) == 4 and line.split()[0].isdigit()] if wave.exists() else []
        cases[name] = dict(status=status, native=native, samples_observed=len(rows),
            last_observed_simulation_time_s=float(rows[-1][1]) if rows else None,
            waveform_observation_is_partial=True)
    paths = [Path(__file__).resolve(), previous_path, assessment, prepared / 'input_manifest.json']
    preparation = dict(directory=str(prepared.relative_to(root)),
        all_noncapacitive_macro_statements_identical=True,
        saved_initial_bias_and_numerical_settings_unchanged=True,
        native_started=False, automatic_launch=False,
        full_finite_R_preserved=True,
        capacitor_branches=proof['corrected_macro_component_counts']['C'],
        original_deadline_uptime=deadline, budget_restarted=False,
        release_qualified=False, adopted=False)
    throughput = previous['throughput_followup']
    throughput.update(corrected_C_full_R_preparation=preparation, active_native_transients=cases)
    followup = previous['restored_self_C_operator_followup']
    followup.update(current_native_engines=live, native_points=cases, active_check_statuses=cases,
                    throughput_followup=throughput)
    previous.update(observed_utc=datetime.now(timezone.utc).isoformat(),
        classification='corrected_substrate_C_full_R_exact_ground_testbench_prepared_non_C_identity_pass_no_additional_native_launch',
        evidence_sha256={str(path.relative_to(root)): digest(path) for path in paths},
        throughput_followup=throughput, restored_self_C_operator_followup=followup,
        native_analog_jobs=live, native_analog_count=len(live),
        current_native_CAD_and_analog_engines=live,
        release_qualified=False, adopted=False, physical_whole_pll_passes=0)
    snapshot = base / 'qualification_progress_071.json'
    assert not snapshot.exists()
    save(snapshot, previous)
    overview = root / 'build/timing450/implementation_assessment.json'
    state = json.loads(overview.read_text())
    state.update(latest_400mhz_qualification_progress=str(snapshot.relative_to(root)),
        active_400mhz_restored_self_C_operator_followup=followup,
        active_400mhz_throughput_followup=throughput,
        release_qualified=False, selected=False, timing_closure_complete=False)
    save(overview, state)
    print('Progress071: corrected-C full-R exact-ground deck prepared and pinned; existing native jobs remain live.')


if __name__ == '__main__':
    main()
