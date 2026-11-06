"""Wait for the IC-only control and compare it to the completed code pulse.

The frequency decomposition is descriptive. The hybrid state is not assumed
reachable, and the pulse also changes boundary histories and switching time.
"""
import argparse
import json
import math
import os
import time
from pathlib import Path
from common_v3 import save, sha, verify
from resources import identity, lease
from assess_selected_detector_prefix import read_prefix
from assess_selected_isolated_control import frequency


def run(swap, pulse_comparison, input_audit, output):
    output.mkdir(parents=True, exist_ok=False)
    os.sched_setaffinity(0, {24})
    save(output/'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid())))
    try:
        comparison = json.loads(pulse_comparison.read_text())
        audit = json.loads(input_audit.read_text())
        for receipt in (comparison, audit):
            verify(receipt['input_sha256'])
        verify(comparison['artifacts'])
        if not (comparison['normal_native_completions'] is True
                and comparison['driver_input_and_output_settled_states_verified'] is True
                and audit['same_physical_cards_sources_reset_solver_and_observation_names'] is True):
            raise ValueError('completed settled pulse and audited IC-only control required')
        manifest = swap/'manifest.json'
        sm = json.loads(manifest.read_text())
        verify(sm['input_sha256'])
        if audit['input_sha256'].get(str(manifest)) != sha(manifest):
            raise ValueError('audit must bind this exact IC-only control')
        if (sm['target_fine'], sm['initial_state_fine'], sm['coarse']) != (112, 111, 20):
            raise ValueError('selected neighboring-code state control required')
        manifests = [Path(p) for p in comparison['input_sha256'] if p.endswith('/manifest.json')]
        if len(manifests) != 3:
            raise ValueError('exact pulse and two static references required')
        folders = {'IC111_static112': swap}
        records = {'IC111_static112': sm}
        paths = [pulse_comparison, input_audit, manifest, swap/'owner.json']
        for path in manifests:
            m = json.loads(path.read_text())
            verify(m['input_sha256'])
            if m['operating_point'] != sm['operating_point']:
                raise ValueError('same device corner, voltage and temperature required')
            if 'fine_sequence' in m:
                if m['fine_sequence'] != [111, 112, 111] or m['coarse'] != 20:
                    raise ValueError('original one-code pulse required')
                key = 'pulse'
            else:
                if m['controls']['coarse'] != 20 or m['controls']['fine'] not in (111, 112):
                    raise ValueError('selected static reference pair required')
                key = 'static'+str(m['controls']['fine'])
            if key in folders:
                raise ValueError('duplicate reference')
            folders[key] = path.parent
            records[key] = m
            if sm['input_sha256'].get(str(path)) != sha(path) and key != 'pulse':
                raise ValueError('IC control must derive from these exact static references')
            paths += [path, path.parent/'status.json', path.parent/'control.raw']
        if set(folders) != {'IC111_static112', 'pulse', 'static111', 'static112'}:
            raise ValueError('complete control/reference inventory required')
        paths += [Path(__file__).resolve(), *(Path(__file__).with_name(n) for n in
                  ('common_v3.py', 'resources.py', 'assess_selected_detector_prefix.py',
                   'assess_selected_isolated_control.py'))]
        pins = {str(p): sha(p) for p in paths}
        save(output/'inputs.json', dict(input_sha256=pins))
        owner = json.loads((swap/'owner.json').read_text())
        deadline = time.clock_gettime(time.CLOCK_BOOTTIME)+11100
        while True:
            state = json.loads((swap/'status.json').read_text())['state']
            if state != 'checkpoint_IC_swap_native_running':
                break
            if identity(owner['pid']) != owner['birth']:
                raise ValueError('control owner stopped without terminal assessment')
            if time.clock_gettime(time.CLOCK_BOOTTIME) > deadline:
                raise TimeoutError('observer deadline; native unchanged')
            save(output/'status.json', dict(state='waiting_for_IC_only_control', release_ready=False))
            time.sleep(10)
        if state != 'checkpoint_IC_swap_assessed':
            raise ValueError('normally completed IC-only control required')
        worker = json.loads((swap/'native.process.json').read_text())
        if identity(worker['pid']) == worker['birth']:
            raise ValueError('native control remains live')
        control = json.loads((swap/'assessment.json').read_text())
        verify(control['input_sha256'])
        verify(control['artifacts'])
        if control['normal_native_completion'] is not True:
            raise ValueError('normal completion required')
        tables = {}
        with lease(1, 2, time.clock_gettime(time.CLOCK_BOOTTIME)+300):
            for key, folder in folders.items():
                raw = folder/'control.raw'
                rows, info = read_prefix(raw, records[key]['observed_roles'])
                if info['incomplete_final_sample_discarded'] or rows[-1][0] < 84e-9:
                    raise ValueError('complete common native horizons required')
                tables[key] = rows
        windows = []
        for start, stop in ((35, 45), (40, 55), (45, 55), (50, 59)):
            f = {key: frequency(rows, start, stop)['frequency_mhz'] for key, rows in tables.items()}
            if not all(math.isfinite(v) and v > 0 for v in f.values()):
                raise ValueError('finite positive measured frequencies required')
            static_increment = f['static112']-f['static111']
            if static_increment <= 0:
                raise ValueError('increasing measured static tuning pair required')
            state_shift = f['IC111_static112']-f['static112']
            residual = f['pulse']-f['IC111_static112']
            windows.append(dict(window_ns=[start, stop], frequency_MHz=f,
                static_increment_MHz=static_increment,
                switched_increment_MHz=f['pulse']-f['static111'],
                IC_only_shift_MHz=state_shift,
                pulse_minus_IC_only_MHz=residual,
                pulse_minus_static112_MHz=f['pulse']-f['static112'],
                IC_only_shift_over_static_increment=state_shift/static_increment,
                residual_over_static_increment=residual/static_increment))
        pins.update({str(swap/n): sha(swap/n) for n in
                     ('assessment.json', 'status.json', 'native.process.json', 'control.raw')})
        verify(pins)
        save(output/'assessment.json', dict(input_sha256=pins, windows=windows,
            normal_native_completions=True, same_simulation_age_windows=True,
            scope='One TT partition. IC-only response holds the static112 exterior fixed; '
                  'pulse starts from111, switches later and retains111 exterior histories. '
                  'The algebraic state/residual decomposition does not isolate causal interactions.',
            hybrid_state_physical_reachability_assumed=False,
            discrepancy_cause_identified=False, full_native_switched_reference_available=False,
            universal_gain_correction_inferred=False, uniform_model_uncertainty_qualified=False,
            release_ready=False))
        save(output/'status.json', dict(state='checkpoint_state_control_compared', release_ready=False))
    except BaseException as error:
        save(output/'status.json', dict(state='stopped_without_qualification',
             reason=repr(error), native_unchanged=True, release_ready=False))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('swap', 'pulse-comparison', 'input-audit', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    run(args.swap.resolve(), args.pulse_comparison.resolve(), args.input_audit.resolve(), args.output.resolve())
