#!/usr/bin/env python3
"""Native sampled BBPD plus mapped receiver PVT screen; no whole-PLL claim."""
import argparse
import concurrent.futures
import itertools
import json
import math
from pathlib import Path
import subprocess
from characterize_bbpd import sha, verify, deck, measure, crossings


def coupled_deck(pdk, model, fixture, corner, supply, temperature, phase, edge):
    text = deck(pdk, model, corner, supply, temperature, phase, edge, [.189715251, .166840822])
    text = '\n'.join(line for line in text.splitlines() if not line.startswith(('CUP ', 'CDN '))) + '\n'
    text = text.replace('.param VDD=', f'.include "{fixture}"\n.param VDD=')
    text = text.replace('.options timeint', 'Xreceiver BBPD[0] BBPD[1] RESET_N VGND VNB VPB VPWR UPQ DNQ bbpd_receiver\n.options timeint')
    text = text.replace('.print tran format=std ', '.print tran format=std precision=16 ')
    text = text.replace('i(VVPWR)', 'v(UPQ) v(DNQ)')
    return text


def read_coupled_rows(path):
    text = path.read_text()
    rows = []
    for line in text.splitlines()[1:]:
        fields = line.split()
        if fields and fields[0].isdigit():
            row = list(map(float, fields))
            if len(row) != 8 or not all(map(math.isfinite, row)):
                raise RuntimeError('Malformed or nonfinite coupled waveform')
            rows.append(row)
    if (not rows or rows[0][1] != 0 or rows[-1][1] < 90e-9 - 1e-14
            or any(b[1] <= a[1] for a, b in zip(rows, rows[1:]))
            or 'End of Xyce(TM) Simulation' not in text):
        raise RuntimeError('Incomplete or nonmonotone coupled waveform')
    return rows


def capture_metrics(rows, supply, phase):
    if phase == 0:
        raise RuntimeError('Signed capture screen requires a nonzero phase')
    expected = 'DN' if phase < 0 else 'UP'
    initial = [r for r in rows if 5e-9 <= r[1] <= 8e-9]
    first = [r for r in rows if 25e-9 <= r[1] <= 29e-9]
    second = [r for r in rows if 65e-9 <= r[1] <= 69e-9]
    if not initial or not first or not second:
        raise RuntimeError('Missing receiver settling sample window')
    edge_metrics = {}
    passes = []
    for name, column in (('UP', 6), ('DN', 7)):
        rise, fall = crossings(rows, column, supply * .5)
        initialized = all(r[column] < .1 * supply for r in initial)
        if name == expected:
            passed = (initialized and len(rise) == len(fall) == 1
                      and 10e-9 <= rise[0] <= 25e-9
                      and 50e-9 <= fall[0] <= 65e-9
                      and all(r[column] > .8 * supply for r in first)
                      and all(r[column] < .2 * supply for r in second))
        else:
            passed = initialized and not rise and not fall and all(r[column] < .2 * supply
                               for r in rows if 5e-9 <= r[1] <= 85e-9)
        passes.append(passed)
        edge_metrics[name] = {'rising_edges_ns': [t * 1e9 for t in rise],
                              'falling_edges_ns': [t * 1e9 for t in fall],
                              'initialized_low': initialized, 'expected_capture_screen_pass': bool(passed)}
    return {'expected_direction': expected, 'receiver_events': edge_metrics,
            'direction_and_two_event_capture_pass': all(passes),
            'bbpd_waveforms': measure(rows, supply)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sampled-directory', type=Path, required=True)
    parser.add_argument('--receiver-directory', type=Path, required=True)
    parser.add_argument('--pdk', type=Path, required=True)
    parser.add_argument('--xyce', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--jobs', type=int, default=2)
    args = parser.parse_args()
    if args.jobs < 1 or args.output.exists():
        raise RuntimeError('Require positive worker count and a fresh output directory')
    args.output.mkdir(parents=True)
    macro = args.sampled_directory.resolve()
    fixture = args.receiver_directory.resolve()
    prior_manifest = macro / 'loaded_ss125/input_manifest.json'
    physical = macro / 'physical_assessment.json'
    extraction = fixture / 'extraction.json'
    pins = {}
    for receipt in (prior_manifest, physical, extraction):
        source = json.loads(receipt.read_text())
        verify(source['sha256'])
        pins.update(source['sha256'])
        pins[str(receipt)] = sha(receipt)
    for source in (Path(__file__).resolve(), Path(__file__).with_name('characterize_bbpd.py'), args.xyce.resolve()):
        pins[str(source)] = sha(source)
    model = macro / 'loaded_ss125/IntegerPLL_BBPD.reduced.spice'
    assert 'sky130_fd_pr__diode' not in model.read_text()
    output = args.output.resolve()
    jobs = []
    for corner, supply, temperature, phase, edge in itertools.product(
            ('ss', 'tt', 'ff', 'sf', 'fs'), (1.62, 1.8, 1.95), (-40, 27, 125), (-200, 200), (20, 200)):
        directory = output / f'{corner}_{supply:g}V_{temperature}C_phase{phase}ps_edge{edge}ps'
        directory.mkdir()
        circuit = directory / 'loaded.cir'
        circuit.write_text(coupled_deck(args.pdk.resolve(), model, fixture / 'receiver.spice',
                                       corner, supply, temperature, phase, edge))
        pins[str(circuit)] = sha(circuit)
        jobs.append((directory, corner, supply, temperature, phase, edge))
    verify(pins)
    manifest = output / 'input_manifest.json'
    manifest.write_text(json.dumps({'sha256': pins, 'requested_points': len(jobs),
                                  'receiver_extraction_limitations': json.loads(extraction.read_text())['limitations']}, indent=2) + '\n')

    def run(job):
        directory, corner, supply, temperature, phase, edge = job
        with (directory / 'run.log').open('w') as log:
            native = subprocess.run([str(args.xyce.resolve()), '-linsolv', 'KLU', '-quiet', '-o',
                                     str(directory / 'loaded'), str(directory / 'loaded.cir')],
                                    stdout=log, stderr=subprocess.STDOUT)
        point = dict(corner=corner, supply_v=supply, temperature_c=temperature, phase_ps=phase,
                     edge_ps=edge, exit_code=native.returncode, simulation_completed=False,
                     direction_and_two_event_capture_pass=False, release_qualified=False, selected=False)
        log = (directory / 'run.log').read_text()
        if native.returncode == 0 and not any(s in log for s in ('Unrecognized dot line', 'Simulation aborted', 'Netlist error')):
            try:
                metrics = capture_metrics(read_coupled_rows(directory / 'loaded.prn'), supply, phase)
                point.update(metrics, simulation_completed=True)
            except (RuntimeError, ValueError, OSError) as error:
                point['error'] = str(error)
        point['sha256'] = {str(p): sha(p) for p in (directory / 'loaded.cir', directory / 'run.log',
                                                   directory / 'loaded.prn') if p.exists()}
        receipt = directory / 'assessment.json'
        receipt.write_text(json.dumps(point, indent=2) + '\n')
        print(json.dumps({k: v for k, v in point.items() if k not in ('sha256', 'bbpd_waveforms', 'receiver_events')}), flush=True)
        return receipt, point

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        results = list(pool.map(run, jobs))
    verify(pins)
    result = {'requested_points': len(jobs), 'completed_points': sum(p['simulation_completed'] for _, p in results),
              'all_simulations_completed': all(p['simulation_completed'] for _, p in results),
              'all_direction_and_two_event_capture_screens_pass': all(p['direction_and_two_event_capture_pass'] for _, p in results),
              'input_manifest_sha256': sha(manifest), 'receipts': {str(r): sha(r) for r, _ in results},
              'release_qualified': False, 'selected': False,
              'scope': '45 primitive PVT points, +/-200 ps, 20/200 ps inputs, two events, mapped nonlinear receiver with fixed max routed RC',
              'limitations': ['Fixed extracted RC and static omitted aggressors',
                              'No full synchronizer coupling or metastability probability/settling proof',
                              'Ideal rails; no current/power/noise or whole-PLL phase/lock/jitter qualification']}
    (output / 'assessment.json').write_text(json.dumps(result, indent=2) + '\n')
    if not result['all_simulations_completed']:
        raise RuntimeError('Native coupled PVT campaign has incomplete simulations')


if __name__ == '__main__':
    main()
