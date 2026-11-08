"""Observe isolated extracted asynchronous-reset pulse capture; qualify no bound."""
import argparse
import json
import math
import os
from pathlib import Path
import time

import numpy as np
from common_v3 import ROOT, save, sha, verify
from compiled_charge_v2 import execute
from prepare_prototype_analog_reference import subcircuits
from prepare_prototype_BBPD_receiver_v2 import header
from resources import identity, lease
from run_prototype_capture_boundaries_v3 import pwl, transition

LOADS = {'dfrtp_1': 250, 'dfrtp_2': 400, 'dfrtp_4': 600,
         'dfstp_1': 125, 'dfstp_2': 400}
PULSES = [(width, ramp) for ramp in (20, 400)
          for width in (100, 400, 1000, 2000) if width >= ramp]


def stable(values, state):
    return bool(len(values)) and bool(np.all(np.isfinite(values))) and bool(
        np.all(values >= 1.62) if state else np.all(values <= .18))


def assess(times, q, control, reset_state, negative_control):
    if (len(times) < 2 or len(q) != len(times) or len(control) != len(times)
            or not all(np.all(np.isfinite(v)) for v in (times, q, control))
            or times[0] != 0 or abs(times[-1] - 22e-9) > 1e-15
            or not np.all(np.diff(times) > 0)):
        raise ValueError('complete finite ordered waveform required')
    pre = (times >= 8e-9) & (times <= 9e-9)
    final = (times >= 18e-9) & (times <= 21e-9)
    expected = 1 - reset_state if negative_control else reset_state
    initialized = stable(q[pre], 1 - reset_state)
    retained = stable(q[final], expected)
    released = stable(control[final], 1)
    low = times[control <= .18]
    asserted_after_initialization = bool(np.any(low >= 9e-9))
    stimulus_correct = asserted_after_initialization != negative_control
    return dict(opposite_prestate_verified=initialized, final_state_verified=retained,
                reset_released_verified=released, stimulus_verified=stimulus_correct,
                fixture_passed=initialized and retained and released and stimulus_correct,
                negative_control=negative_control)


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    os.sched_setaffinity(0, {17})
    os.environ.update(OMP_NUM_THREADS='1', OMP_THREAD_LIMIT='1', OPENBLAS_NUM_THREADS='1')
    save(output / 'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid())) )
    try:
        extraction = ROOT / 'build/signoff400/prototype_v3_fixed_divider_digital_capacitance_001'
        receipt = extraction / 'assessment.json'
        source = extraction / 'IntegerPLL_ProgrammedCore/capacitance.spice'
        a = json.loads(receipt.read_text())
        if a['artifacts'].get(str(source)) != sha(source):
            raise ValueError('extracted cell source changed')
        blocks = subcircuits(source.read_text())
        model = output / 'cells.spice'
        model.write_text('\n'.join(blocks['sky130_fd_sc_hs__' + name] for name in LOADS))
        ng = ROOT / 'build/tools/ngspice47_diode_charge_fix_001/ngspice'
        pdk = Path('/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.tech/ngspice/sky130.lib.spice')
        pins = {str(p): sha(p) for p in [receipt, source, model, ng, pdk, Path(__file__).resolve(),
                Path(__file__).with_name('prepare_prototype_analog_reference.py'),
                Path(__file__).with_name('prepare_prototype_BBPD_receiver_v2.py'),
                Path(__file__).with_name('run_prototype_capture_boundaries_v3.py')]}
        cases, body = [], []
        for short, load in LOADS.items():
            master = 'sky130_fd_sc_hs__' + short
            block = blocks[master]
            if any(line.lstrip().startswith('D') for line in block.splitlines()):
                raise ValueError('extracted diode units need separate review')
            ports = header(block)
            reset_state = int(short.startswith('dfstp'))
            for width, ramp in [(0, 20), *PULSES]:
                i = len(cases)
                # Initialize via async control, capture opposite data at 4 ns,
                # then hold CLK low throughout the test pulse and observation.
                ctrl = [(0, 0), (1, 0), (1.2, 1.8)]
                if width:
                    ctrl += transition(10, 1, 0, ramp)
                    ctrl += transition(10 + width / 1000, 0, 1, ramp)
                ctrl += [(22, 1.8)]
                binding = dict(CLK='CLK', D=f'D{i}', Q=f'Q{i}', RESET_B=f'CTRL{i}',
                               SET_B=f'CTRL{i}', VGND='0', VNB='0', VPB='VDD', VPWR='VDD')
                body += [f'VC{i} CTRL{i} 0 {pwl(ctrl)}',
                         f'VD{i} D{i} 0 {(1-reset_state)*1.8}',
                         f'XC{i} ' + ' '.join(binding.get(p, f'private_{i}_{j}')
                             for j, p in enumerate(ports)) + ' ' + master,
                         f'CL{i} Q{i} 0 {load}f']
                cases.append(dict(master=master, load_fF=load, width_ps=width,
                                  full_ramp_ps=ramp, reset_state=reset_state,
                                  negative_control=width == 0))
        artifacts, results = {}, []
        save(output / 'plan.json', dict(cases=cases, corners=['tt','ff','ss','sf','fs'],
             maximum_step_ps=2, temperature_C=27, supply_V=1.8,
             clock_held_low_during_pulse=True, automatic_identical_retry=False,
             physical_reset_timing_qualified=False, release_ready=False))
        pins[str(output / 'plan.json')] = sha(output / 'plan.json')
        for corner in ('tt', 'ff', 'ss', 'sf', 'fs'):
            target = output / corner
            target.mkdir()
            data, deck = target / 'waveform.dat', target / 'reset.cir'
            init = target / '.spiceinit'
            init.write_text('set ngbehavior=hsa\n')
            deck.write_text('\n'.join(['* Isolated extracted reset-pulse fixtures',
                f'.lib "{pdk}" {corner}', f'.include "{model}"', '.temp 27',
                '.option reltol=1e-5 abstol=1e-9 num_threads=1', 'VDD VDD 0 1.8',
                'VCLK CLK 0 PWL(0 0 3.9n 0 4.1n 1.8 4.9n 1.8 5.1n 0)',
                *body, '.control', 'set wr_singlescale', 'set wr_vecnames',
                'set numdgt=15', 'tran 2p 22n 0 2p', f'wrdata {data} ' +
                ' '.join([f'v(q{i})' for i in range(len(cases))] +
                         [f'v(ctrl{i})' for i in range(len(cases))]),
                'quit', '.endc', '.end']) + '\n')
            pins.update({str(p): sha(p) for p in [deck, init]})
            save(output / 'status.json', dict(state='native_reset_pulse_grid_running', corner=corner, release_ready=False))
            with lease(1, 4, time.clock_gettime(time.CLOCK_BOOTTIME) + 86400):
                previous_directory = Path.cwd()
                try:
                    os.chdir(target)
                    execute([ng, '-b', deck], target / 'native.log',
                            time.clock_gettime(time.CLOCK_BOOTTIME) + 3600, 4)
                finally:
                    os.chdir(previous_directory)
            expected = ['time'] + [f'v(q{i})' for i in range(len(cases))] + [f'v(ctrl{i})' for i in range(len(cases))]
            if data.open().readline().split() != expected:
                raise ValueError('unexpected saved columns')
            values = np.loadtxt(data, skiprows=1)
            for i, case in enumerate(cases):
                results.append(dict(corner=corner, **case, **assess(values[:,0], values[:,i+1],
                    values[:,len(cases)+i+1], case['reset_state'], case['negative_control'])))
            artifacts.update({str(p): sha(p) for p in [data, target / 'native.log']})
        detail = output / 'observations.json'
        save(detail, results)
        artifacts[str(detail)] = sha(detail)
        verify(pins)
        save(output / 'assessment.json', dict(input_sha256=pins, artifacts=artifacts,
             cases=len(results), failed_cases=sum(not r['fixture_passed'] for r in results),
             all_grid_fixtures_pass=all(r['fixture_passed'] for r in results),
             independent_fixture_only=True, reset_slew_and_load_envelope_qualified=False,
             minimum_pulse_bound_qualified=False, recovery_removal_qualified=False,
             routed_reset_timing_qualified=False, release_ready=False))
        save(output / 'status.json', dict(state='native_reset_pulse_grid_complete', release_ready=False))
    except BaseException as error:
        save(output / 'status.json', dict(state='stopped_without_qualification', reason=repr(error), release_ready=False))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    run(parser.parse_args().output.resolve())
