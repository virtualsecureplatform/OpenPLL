"""Compare completed 50 ps prescribed-boundary replays to a completed full 10 ps trace."""
import os
os.environ.update(OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', OMP_THREAD_LIMIT='1')
import argparse
import json
from pathlib import Path
import time
import numpy as np
from common_v3 import ROOT, save, sha, verify
from resources import identity, lease
from compare_keeper_native_timestep import compare_waveforms
from assess_selected_detector_phase_probe_v2 import read_selected


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    os.sched_setaffinity(0, {30})
    save(output / 'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid())))
    base = ROOT / 'build/signoff400'
    timestep = base / 'selected_keeper_step50_comparison_1280'
    full50 = base / 'selected_keeper_fine149_step50_1278/assessment.json'
    cases = [('reduced_original_receiver', base / 'selected_keeper_aggregate_replay_1403',
              base / 'selected_keeper_capacitor_boundary_reduction_1383'),
             ('reduced_expanded_receiver', base / 'selected_keeper_receiver_replay_1427',
              base / 'selected_keeper_receiver_reduction_1420')]
    try:
        receipt = timestep / 'assessment.json'
        a = json.loads(receipt.read_text())
        if (a.get('electrical_deck_only_max_step_changed') is not True
                or a.get('all_physical_tuning_controls_correct') is not True
                or a['input_sha256'].get(str(full50)) != sha(full50)):
            raise ValueError('completed matched 10/50 ps full controls required')
        files = [receipt, full50, timestep / 'reference.npy', timestep / 'candidate.npy',
                 Path(__file__).resolve(), Path(__file__).with_name('compare_keeper_native_timestep.py'),
                 Path(__file__).with_name('assess_selected_detector_phase_probe_v2.py')]
        for _, replay, reduction in cases:
            files += [replay / 'assessment.json', replay / 'replay.raw', reduction / 'assessment.json', reduction / 'bindings.json']
        pins = {str(path): sha(path) for path in files}
        save(output / 'inputs.json', dict(input_sha256=pins, CPU=30, memory_GiB=2,
             native_simulation_requested=False, completed_output_arrays_reused=True,
             reference_timestep_ps=10, replay_timestep_ps=50, release_ready=False))
        save(output / 'status.json', dict(state='verifying_completed_timestep_and_replay_inputs', release_ready=False))
        with lease(1, 2, time.clock_gettime(time.CLOCK_BOOTTIME) + 86400):
            verify(a['input_sha256'])
            verify(a['artifacts'])
            reference = np.load(timestep / 'reference.npy', mmap_mode='r')
            candidate = np.load(timestep / 'candidate.npy', mmap_mode='r')
            full_metrics = compare_waveforms(reference, candidate)
            if abs(full_metrics['frequency_difference_ppm'] - a['frequency_difference_ppm']) > 1e-6:
                raise ValueError('saved completed arrays disagree with retained timestep result')
            results = []
            for label, replay, reduction in cases:
                r = json.loads((replay / 'assessment.json').read_text())
                d = json.loads((reduction / 'assessment.json').read_text())
                for value in (r, d):
                    verify(value['input_sha256'])
                    verify(value['artifacts'])
                if (r.get('normal_native_replay_complete') is not True
                        or r.get('all_saved_replay_values_finite') is not True
                        or r.get('PLLOUT_forced') is not False or r.get('max_step_ps') != 50
                        or r.get('native_executable_sha256') != 'e07a45abe62b01ea1c47a470facf0da02e9de3cfb8a7448ce4cd7e5febf64816'
                        or r['input_sha256'].get(str(full50)) != sha(full50)
                        or r['input_sha256'].get(str(reduction / 'assessment.json')) != sha(reduction / 'assessment.json')):
                    raise ValueError('matching completed old-backend 50 ps replay and reduction required')
                binding = json.loads((reduction / 'bindings.json').read_text())['observation_only_ports']['PLLOUT']
                rows = np.asarray(read_selected(replay / 'replay.raw', {'PLLOUT': binding}, 260e-9))
                versus10 = compare_waveforms(reference, rows)
                versus50 = compare_waveforms(candidate, rows)
                chained = 1e6 * ((1 + versus50['frequency_difference_ppm'] / 1e6)
                                 * (1 + full_metrics['frequency_difference_ppm'] / 1e6) - 1)
                if abs(chained - versus10['frequency_difference_ppm']) > 1e-6:
                    raise ValueError('frequency-ratio accounting inconsistent')
                results.append(dict(case=label, compared_to_full_step10=versus10,
                                    compared_to_full_step50=versus50,
                                    multiplicative_frequency_ratio_accounting_verified=True))
            verify(pins)
        save(output / 'assessment.json', dict(input_sha256=pins, artifacts={},
             full_step50_vs_step10=full_metrics, replay_comparisons=results,
             completed_saved_arrays_reused=True, additional_native_simulations=0,
             replay_forcing_still_from_full_step50=True, source_histories_differ_from_step10=True,
             error_components_are_not_independent_bounds=True, finer_step_convergence_available=False,
             corrected_backend_characterized=False, changed_controller_prediction_qualified=False,
             numerical_accuracy_qualified=False, model_qualified=False, release_ready=False))
        save(output / 'status.json', dict(state='completed_replays_compared_to_full_step10', release_ready=False))
    except BaseException as error:
        save(output / 'status.json', dict(state='stopped_without_qualification', reason=repr(error), release_ready=False))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output.resolve())
