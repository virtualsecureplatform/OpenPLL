#!/usr/bin/env python3
"""Prepare one independent longer-duration DCO observation, without launching it.

Keeps the completed80ns circuit, initialization, solver settings and step limit.
Only the transient stop time changes; all original measurement directives are
removed and every predeclared observation window is retained for later audit.
No new frequency model or measurement window is adopted.
"""
import argparse
import json
from pathlib import Path
import re

from characterize_compact_propagation import XYCE
from run_dco_qualification import ROOT, REQUIREMENTS, sha, save


def extend_deck(text, stop_ns):
    assert stop_ns in (160, 200)
    original = text.splitlines()
    # Measurements are instrumentation, not circuit/device/initial conditions.
    lines = [line for line in original if not re.match(r'^\s*\.meas(?:ure)?\b', line, re.I)]
    declarations = [line for line in lines if re.match(r'^\s*\.tran\b', line, re.I)]
    assert len(declarations) == 1
    tokens = declarations[0].split()
    assert len(tokens) == 5 and tokens[3] == '0'
    assert [t[-1].lower() for t in (tokens[1], tokens[2], tokens[4])] == ['p', 'n', 'p']
    assert [float(t[:-1]) for t in (tokens[1], tokens[2], tokens[4])] == [10, 80, 10]
    modified = re.sub(r'(?i)^(\s*\.tran\s+\S+\s+)\S+', rf'\g<1>{stop_ns}n', declarations[0])
    result = '\n'.join(modified if line == declarations[0] else line for line in lines)+'\n'
    # Independently restore the old stop time and require exact equality of
    # every remaining statement, including all capacitors and initial states.
    restored = '\n'.join(declarations[0] if line == modified else line for line in result.splitlines())+'\n'
    assert restored == '\n'.join(lines)+'\n'
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--code', required=True, type=int, choices=[128, 247])
    parser.add_argument('--stop-ns', type=int, choices=[160, 200], default=160)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    out = args.output.resolve()
    assert not out.exists()
    screen_path = ROOT/'build/timing450/dco_c1_fine_load_001/screen_160.json'
    screen = json.loads(screen_path.read_text())
    assert screen['native_complete']
    point, = [p for p in screen['points'] if p['code'] == args.code]
    wave = Path(point['waveform'])
    assert sha(wave) == point['waveform_sha256']
    provenance_path = wave.with_suffix('.provenance.json')
    original = wave.with_suffix('.spice')
    provenance = json.loads(provenance_path.read_text())
    assert provenance['completed'] and sha(original) == provenance['netlist_sha256']
    param = provenance['parameters']
    assert param['corner'] == 'tt' and param['temperature_c'] == 27 and param['vdd'] == 1.8
    assert param['coarse_codes'] == '1' and args.code in map(int, param['codes'].split(','))
    assert param['therm_invert'] and param['simulator'] == 'xyce'
    assert param['xyce'] == '/opt/xyce/bin/Xyce -linsolv KLU'
    assert param['sim_time_ns'] == 80 and param['meas_start_ns'] == 20
    assert param['max_step_ps'] == 10 and param['xyce_reltol'] == 1e-5 and param['xyce_abstol'] == 1e-9
    pins = dict(provenance['files'])
    for p in (Path(__file__).resolve(), REQUIREMENTS, screen_path, wave, original, provenance_path, XYCE):
        pins[str(p)] = sha(p)
    for path, digest in pins.items():
        assert sha(path) == digest, path
    text = extend_deck(original.read_text(), args.stop_ns)
    log = wave.with_suffix('.log').read_text()
    elapsed = float(re.findall(r'Total Elapsed Run Time:\s*([0-9.eE+-]+)', log)[-1])
    pins[str(wave.with_suffix('.log'))] = sha(wave.with_suffix('.log'))
    out.mkdir(parents=True, exist_ok=False)
    deck = out/'duration.spice'
    deck.write_text(text)
    pins[str(deck)] = sha(deck)
    windows = [(20, 80), (40, 80), (60, 80)]
    windows += [(start, args.stop_ns) for start in (20, 40, 60, 80, 100)]
    if args.stop_ns == 200:
        windows += [(120, 200), (140, 200)]
    save(out/'plan.json', dict(input_sha256=pins, reference_waveform=str(wave),
        code=args.code, coarse=1, extra_loads=160,
        pvt=dict(corner='tt', temperature_c=27, supply_v=1.8),
        target_mhz=400, reference_stop_ns=80, stop_ns=args.stop_ns,
        predeclared_windows_ns=windows, solver='KLU', thread_policy='OMP/OPENBLAS/MKL=1',
        elapsed_reference_80ns_s=elapsed,
        linear_duration_runtime_projection_s=elapsed*args.stop_ns/80,
        projection_is_not_a_runtime_guarantee=True,
        total_check_budget_s=43200, automatic_identical_retry=False,
        native_execution_started=False, native_execution_queued=False,
        measurement_window_adopted=False, calibration_model_qualified=False,
        release_qualified=False, scope=__doc__))
    print(f'Prepared{args.stop_ns}ns duration comparison atfine{args.code}; no native job launched')


if __name__ == '__main__':
    main()
