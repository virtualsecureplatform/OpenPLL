#!/usr/bin/env python3
"""Screen mapped reset/receiver cell-RC at 45 primitive PVT points and 450 MHz.

The post-withdrawal event check is a physical-stage screen; it does not replace
RTL consumption replay, gate timing, statistical MTBF or whole-PLL qualification.
"""
import argparse
import concurrent.futures
import itertools
import json
import math
import re
import subprocess
from pathlib import Path
from characterize_bbpd import sha, verify, crossings


def read_wave(path):
    text = path.read_text()
    rows = []
    for line in text.splitlines()[1:]:
        fields = line.split()
        if fields and fields[0].isdigit():
            row = list(map(float, fields))
            if len(row) != 22 or not all(map(math.isfinite, row)):
                raise RuntimeError('Malformed mapped-reset waveform')
            rows.append(row)
    if (not rows or rows[0][1] != 0 or rows[-1][1] < 90e-9 - 1e-14
            or any(b[1] <= a[1] for a, b in zip(rows, rows[1:]))
            or 'End of Xyce(TM) Simulation' not in text):
        raise RuntimeError('Incomplete/nonmonotone mapped-reset waveform')
    return rows


def metrics(rows, supply, phase):
    threshold = supply / 2
    edges = {name: crossings(rows, column, threshold, start=0, stop=90e-9)
             for name, column in (('UP2', 9), ('DN2', 11), ('READY2', 17),
                                  ('EVENT_RESET', 18), ('TRACK_ACTIVE', 20), ('COMMAND_RUN', 21))}
    command = edges['COMMAND_RUN']
    if len(command[0]) != 1 or len(command[1]) != 1:
        raise RuntimeError('Command withdrawal waveform differs from recipe')
    width = (command[0][0] - command[1][0]) * 1e9
    if abs(width - 1.5) > 1e-7:
        raise RuntimeError('Command low-width differs from 1.500 ns')
    expected = 'UP2' if phase > 0 else 'DN2'
    opposite = 'DN2' if phase > 0 else 'UP2'
    post = {name: sorted(t for pair in edges[name] for t in pair if 50e-9 <= t <= 85e-9)
            for name in ('UP2', 'DN2')}
    window = [r for r in rows if 50e-9 <= r[1] <= 85e-9]
    ready_stable = bool(window) and all(r[17] > .8 * supply and r[20] > .8 * supply for r in window)
    opposite_column = 11 if phase > 0 else 9
    opposite_quiet = all(abs(r[opposite_column]) < .2 * supply for r in rows)
    reset = edges['EVENT_RESET']
    pairs = [(fall, rise) for fall in reset[1] for rise in reset[0]
             if 17e-9 <= fall < rise < 45e-9]
    guard = edges['READY2']
    guard_pairs = [(fall, rise) for fall in guard[1] for rise in guard[0]
                   if 17e-9 <= fall < rise < 45e-9]
    initialized = rows[0][9] < .2 * supply and rows[0][11] < .2 * supply
    passed = (initialized and ready_stable and opposite_quiet and len(pairs) == 1
              and len(guard_pairs) == 1 and len(post[expected]) == 1 and not post[opposite])
    return {'expected_direction': expected[:2], 'command_low_width_ns': width,
            'event_reset_low_width_ns': (pairs[0][1] - pairs[0][0]) * 1e9 if len(pairs) == 1 else None,
            'guard_low_width_ns': (guard_pairs[0][1] - guard_pairs[0][0]) * 1e9 if len(guard_pairs) == 1 else None,
            'post_withdrawal_event_crossings_ns': {k: [t * 1e9 for t in v] for k, v in post.items()},
            'post_window_capture_and_guard_screen_pass': passed,
            'signal_edges_ns': {k: {'rising': [t * 1e9 for t in v[0]],
                                    'falling': [t * 1e9 for t in v[1]]} for k, v in edges.items()}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prototype', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--xyce', type=Path, default=Path('/opt/xyce/bin/Xyce'))
    parser.add_argument('--jobs', type=int, default=4)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 8:
        parser.error('jobs must be between 1 and 8')
    prototype = args.prototype.resolve()
    native = json.loads((prototype / 'assessment.json').read_text())
    assert native['exit_code'] == 0 and native['simulation_completed']
    verify(native['sha256'])
    manifest = prototype / 'input_manifest.json'
    assert sha(manifest) == native['input_manifest_sha256']
    pins = json.loads(manifest.read_text())['sha256']
    verify(pins)
    for path in (manifest, prototype / 'assessment.json', Path(__file__).resolve(),
                 Path(__file__).with_name('characterize_bbpd.py'), args.xyce):
        pins[str(path.resolve())] = sha(path)
    control = metrics(read_wave(prototype / 'loaded.prn'), 1.62, 250)
    assert control['post_window_capture_and_guard_screen_pass']
    original = (prototype / 'loaded.cir').read_text()
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / 'prototype_control.json').write_text(json.dumps(control, indent=2) + '\n')
    jobs = []
    for corner, supply, temperature, phase, edge in itertools.product(
            ('ss', 'tt', 'ff', 'sf', 'fs'), (1.62, 1.8, 1.95), (-40, 27, 125), (-250, 250), (20, 200)):
        folder = args.output / f'{corner}_{supply:g}V_{temperature}C_phase{phase}ps_edge{edge}ps'
        folder.mkdir()
        text, count = re.subn(r'(?m)^(\.lib "[^\n]+") ss$', rf'\1 {corner}', original)
        assert count == 1
        for old, new in (('.param VDD=1.62', f'.param VDD={supply:g}'),
                         ('.options device temp=125', f'.options device temp={temperature}'),
                         ('VREF REF 0 PULSE(0 {VDD} 10n 20p 20p 20n 40n)',
                          f'VREF REF 0 PULSE(0 {{VDD}} 10n {edge}p {edge}p 20n 40n)'),
                         ('VDIV CLKDIVR 0 PULSE(0 {VDD} 10.25n 20p 20p 20n 40n)',
                          f'VDIV CLKDIVR 0 PULSE(0 {{VDD}} {10+phase/1000:g}n {edge}p {edge}p 20n 40n)')):
            assert text.count(old) == 1
            text = text.replace(old, new)
        text = '* Mapped reset/receiver diagnostic; nominal internal cellRC, max routeRC, ideal controls/PLL.\n' + text.split('\n', 1)[1]
        circuit = folder / 'loaded.cir'
        circuit.write_text(text)
        pins[str(circuit.resolve())] = sha(circuit)
        jobs.append((folder, corner, supply, temperature, phase, edge))
    verify(pins)
    manifest = args.output / 'input_manifest.json'
    manifest.write_text(json.dumps({'sha256': pins, 'requested_points': len(jobs),
        'scope': '45 primitivePVT x +/-250ps x20/200ps REF/DIV edges,450MHz ideal200ps PLL,nominal internal cellRC,max routeRC,1.500ns committedRUN withdrawal; measure one fresh signed stage event in50..85ns; no fullPLL/MTBF qualification'}, indent=2) + '\n')

    def run(job):
        folder, corner, supply, temperature, phase, edge = job
        with (folder / 'run.log').open('w') as log:
            result = subprocess.run([str(args.xyce), '-linsolv', 'KLU', '-quiet', '-o',
                                     str(folder / 'loaded'), str(folder / 'loaded.cir')],
                                    stdout=log, stderr=subprocess.STDOUT)
        record = dict(corner=corner, supply_v=supply, temperature_c=temperature,
                      phase_ps=phase, edge_ps=edge, exit_code=result.returncode,
                      simulation_completed=False, post_window_capture_and_guard_screen_pass=False,
                      release_qualified=False, selected=False)
        log_text = (folder / 'run.log').read_text()
        if result.returncode == 0 and not any(e in log_text for e in ('Unrecognized dot line', 'Simulation aborted', 'Netlist error')):
            try:
                record.update(metrics(read_wave(folder / 'loaded.prn'), supply, phase), simulation_completed=True)
            except (RuntimeError, ValueError, OSError) as error:
                record['error'] = str(error)
        record['sha256'] = {str(p.resolve()): sha(p) for p in (folder / 'loaded.cir', folder / 'run.log', folder / 'loaded.prn') if p.exists()}
        receipt = folder / 'assessment.json'
        receipt.write_text(json.dumps(record, indent=2) + '\n')
        print(json.dumps({k: v for k, v in record.items() if k not in ('sha256', 'signal_edges_ns')}), flush=True)
        return receipt, record

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        results = list(pool.map(run, jobs))
    verify(pins)
    report = {'requested_points': len(jobs), 'completed_points': sum(r['simulation_completed'] for _, r in results),
              'all_post_window_capture_and_guard_screens_pass': all(r['post_window_capture_and_guard_screen_pass'] for _, r in results),
              'receipts': {str(p.resolve()): sha(p) for p, _ in results},
              'input_manifest_sha256': sha(manifest), 'release_qualified': False, 'selected': False,
              'limitations': ['Only450MHz and one withdrawal alignment; cellRC nominal, routedRC fixed max',
                              'Ideal external reset/committed controls/PLL/ties; acquisition and BBPD reset export omitted',
                              'Stage waveforms require separate RTL consumption replay; pre-withdrawal events may be legitimate',
                              'No statistical metastability, measured supply noise or wholePLL proof']}
    (args.output / 'assessment.json').write_text(json.dumps(report, indent=2) + '\n')
    if report['completed_points'] != len(jobs):
        raise RuntimeError('Incomplete mapped reset PVT campaign')


if __name__ == '__main__':
    main()
