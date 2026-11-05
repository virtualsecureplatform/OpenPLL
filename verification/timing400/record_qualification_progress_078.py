#!/usr/bin/env python3
"""Record stock threaded solver preparation and full-order ROM capacity audit."""
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
    previous_path = base / 'qualification_progress_077.json'
    previous = json.loads(previous_path.read_text())
    build = base / 'stock_threaded_Xyce_001'
    queued = base / 'stock_threaded_solver_controls_001'
    pipeline = {}
    paths = [Path(__file__).resolve(), owner, previous_path, build / 'input_manifest.json',
        Path(__file__).with_name('build_stock_threaded_Xyce.py'),
        Path(__file__).with_name('check_stock_threaded_solver_controls.py')]
    for folder in [build, queued]:
        status = json.loads((folder / 'status.json').read_text())
        handle = process(status['runner_pid'])
        assert handle['live']
        assert json.loads((folder / 'owner.json').read_text())['deadline_uptime'] == deadline
        pipeline[folder.name] = dict(status=status, runner=handle)
        paths.append(folder / 'owner.json')
    receipts = json.loads((build / 'stage_receipts.json').read_text())
    assert len(receipts) >= 6 and all(row['exit_code'] == 0 for row in receipts[:6])
    manifest = json.loads((build / 'input_manifest.json').read_text())
    assert manifest['threaded_solver'] == 'SHYLU_BASKER' and manifest['build_workers'] == 4
    rom_source = Path('/opt/Xyce/src/DeviceModelPKG/OpenModels/N_DEV_ROM.C')
    basker_source = Path('/opt/Trilinos/packages/amesos2/src/Amesos2_Basker_decl.hpp')
    threaded_source = Path('/opt/Trilinos/packages/amesos2/src/Amesos2_ShyLUBasker_def.hpp')
    rom = rom_source.read_text()
    assert 'Bhat.resize( M*N )' in rom and 'Lhat.resize( M*N )' in rom
    assert 'BaskerClassicNS::BaskerClassic' in basker_source.read_text()
    assert 'Kokkos::OpenMP' in threaded_source.read_text() and 'use_nodeNDP' in threaded_source.read_text()
    paths.extend([rom_source, basker_source, threaded_source])
    physical_bytes = int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines()
                              if line.startswith('MemTotal:'))) * 1024
    dense_bytes = 2 * 148346 * 34412 * 8
    assert dense_bytes > physical_bytes
    work = previous['throughput_followup']
    work['threaded_solver_followup'] = dict(
        stock_backend='SHYLU_BASKER', distinct_from_prior_classic_BASKER=True,
        OpenMP_METIS_stock_build_in_progress=True, pipeline=pipeline,
        ordering_source_commits=manifest['ordering_source_commits'],
        successful_dependency_stages_observed=receipts, build_workers=4,
        controls_requested_thread_counts=[1, 8], native_controls_passed=False,
        thread_pool_observation_is_not_factorization_scaling_proof=True,
        active_native_solver_or_circuit_changed=False, full_DCO_performance_improvement_demonstrated=False,
        original_deadline_uptime=deadline, budget_restarted=False, release_qualified=False, adopted=False)
    work['literal_full_order_ROM_capacity_audit'] = dict(
        proposed_states=148346, proposed_ports=34412,
        dense_input_and_output_arrays_bytes=dense_bytes, machine_physical_RAM_bytes=physical_bytes,
        dense_B_and_L_confirmed_in_stock_source=True,
        literal_encoding_rejected_before_launch=True,
        all_possible_alternative_ROM_encodings_ruled_out=False, active_model_changed=False)
    cases, live = {}, []
    for name in ['DCO_domain_nom_tt27_c0_f247_80ns_stock_serial_corrected_002',
                 'DCO_native_zero_wire_R_nom_tt27_c0_f247_25ns_numeric_001']:
        folder = base / name
        status = json.loads((folder / 'status.json').read_text())
        handle = process(status['native_pid'])
        assert handle['live'] and handle['argv'][-1] == str((folder / 'point.cir').resolve())
        live.append(handle)
        text = (folder / 'point.cir.prn').read_text(); lines = text.splitlines()
        if text and not text.endswith('\n'): lines.pop()
        rows = [line.split() for line in lines[1:] if len(line.split()) == 4 and line.split()[0].isdigit()]
        cases[name] = dict(status=status, native=handle, samples_observed=len(rows),
            last_observed_simulation_time_s=float(rows[-1][1]) if rows else None,
            waveform_observation_is_partial=True)
    work['active_native_transients'] = cases
    followup = previous['restored_self_C_operator_followup']
    followup.update(current_native_engines=live, native_points=cases, active_check_statuses=cases,
                    throughput_followup=work)
    previous.update(observed_utc=datetime.now(timezone.utc).isoformat(),
        classification='literal_full_order_ROM_rejected_for_dense_arrays_stock_OpenMP_METIS_ShyLU_build_and_queued_controls_live_existing_native_runs_preserved',
        throughput_followup=work, restored_self_C_operator_followup=followup,
        evidence_sha256={str(path): digest(path) for path in paths},
        native_analog_jobs=live, native_analog_count=len(live), current_native_CAD_and_analog_engines=live,
        release_qualified=False, adopted=False, physical_whole_pll_passes=0)
    snapshot = base / 'qualification_progress_078.json'
    assert not snapshot.exists(); save(snapshot, previous)
    overview = root / 'build/timing450/implementation_assessment.json'
    state = json.loads(overview.read_text())
    state.update(latest_400mhz_qualification_progress=str(snapshot.relative_to(root)),
        active_400mhz_restored_self_C_operator_followup=followup, active_400mhz_throughput_followup=work,
        release_qualified=False, selected=False, timing_closure_complete=False)
    save(overview, state)
    print('Progress078: literal ROM capacity rejected; stock threaded ShyLU preparation and queued controls live, active native circuits unchanged.')


if __name__ == '__main__': main()
