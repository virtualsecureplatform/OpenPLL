#!/usr/bin/env python3
"""One numerical refinement of the measured ambiguous slew fixtures.

Changes maximum step from 2ps to 1ps and tightens tolerances by ten. Reports
raw threshold crossings and delay changes; does not qualify a timing model.
Total 12h includes capacity waiting. No automatic retry or waveform filtering.
"""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import subprocess
import time

from characterize_compact_propagation import XYCE, admit_one, crossings
from check_compact_clock_tree import verify
from run_dco_qualification import sha, save


def main():
    deadline = time.monotonic()+43200
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('batch', 'slew', 'output'):
        parser.add_argument('--'+key, required=True, type=Path)
    args = parser.parse_args()
    batch, slew, out = args.batch.resolve(), args.slew.resolve(), args.output.resolve()
    base = verify(batch/'assessment.json')
    audit = verify(slew/'assessment.json')
    assert base['passing'] == base['fixtures'] and base['all_native_waveform_events_terminal']
    plan = json.loads((batch/'plan.json').read_text())
    selected = [r['case_index'] for r in audit['records'] if not r['passed']]
    assert 0 < len(selected) <= 6
    for i in selected:
        case = plan['fixtures'][i]
        assert case['external_load_pf'] == 0 and case['full_ramp_ps'] == 20
        assert case['master'].split('__')[1].split('_')[0] in ('xor2', 'xnor2')
    out.mkdir(parents=True, exist_ok=False)
    pins = dict(base['input_sha256'])
    for p in [Path(__file__).resolve(), Path(__file__).with_name('characterize_compact_propagation.py'),
              Path(__file__).with_name('check_compact_clock_tree.py'), batch/'assessment.json',
              batch/'plan.json', slew/'assessment.json', XYCE]:
        pins[str(p.resolve())] = sha(p)

    def status(state, **fields):
        save(out/'status.json', dict(observed_utc=datetime.now(timezone.utc).isoformat(),
             state=state, per_check_total_budget_s=43200, release_qualified=False, **fields))

    def remaining():
        value = deadline-time.monotonic()
        if value <= 0:
            status('timeout_inconclusive')
            raise TimeoutError('total refinement budget reached')
        return value

    lines = (batch/'batch.cir').read_text().splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith('VIN_0 '))
    header = lines[:start]
    assert header.count('.options timeint reltol=1e-5 abstol=1e-10') == 1
    header[0] = '* Focused numerical refinement of terminal ambiguous slew fixtures'
    header = [line.replace('reltol=1e-5 abstol=1e-10', 'reltol=1e-6 abstol=1e-11') for line in header]
    body = []
    for line in lines[start:]:
        match = re.match(r'^(VIN|XDUT|CLOAD)_(\d+)\s', line)
        if match and int(match[2]) in selected:
            body.append(line)
    assert len(body) == 2*len(selected), 'expected zero-load input and DUT only'
    columns = [f'V({kind}_{i})' for i in selected for kind in ('IN', 'OUT')]
    deck = out/'batch.cir'
    deck.write_text('\n'.join(header+body+['.tran 1p 34n 0 1p', '.print tran '+' '.join(columns), '.end'])+'\n')
    pins[str(deck)] = sha(deck)
    save(out/'plan.json', dict(selected_case_indices=selected, pvt=plan['pvt'],
        input_sha256=pins, changes=dict(max_step_ps=[2, 1], reltol=[1e-5, 1e-6], abstol=[1e-10, 1e-11]),
        source_fixtures=[plan['fixtures'][i] for i in selected], automatic_identical_retry=False,
        scope=__doc__, release_qualified=False))
    for path, digest in pins.items():
        assert sha(Path(path)) == digest, path
    while True:
        remaining()
        try:
            admit_one(out)
            break
        except AssertionError as error:
            status('waiting_for_native_capacity', reason=str(error))
            time.sleep(min(30, remaining()))
    command = [str(XYCE), '-linsolv', 'KLU', '-quiet', '-o', str(out/'batch'), str(deck)]
    with (out/'run.log').open('x') as stream:
        child = subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT)
        save(out/'launch.json', dict(pid=child.pid, command=command, input_sha256=pins,
                                   total_budget_s=43200, release_qualified=False))
        status('native_running', native_pid=child.pid)
        try:
            code = child.wait(timeout=remaining())
        except subprocess.TimeoutExpired:
            child.terminate()
            try:
                child.wait(timeout=30)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
            status('timeout_inconclusive', native_pid=child.pid)
            return
    assert code == 0, (out/'run.log').read_text()[-2000:]
    status('assessing_terminal_native_waveform')
    times, values, terminal = [], [[] for _ in columns], False
    with (out/'batch.prn').open() as stream:
        assert stream.readline().split() == ['Index', 'TIME', *columns]
        for line in stream:
            if 'End of Xyce(TM) Simulation' in line:
                assert not terminal
                terminal = True
                continue
            row = line.split()
            if not row:
                continue
            assert not terminal and row[0].isdigit() and int(row[0]) == len(times)
            numbers = list(map(float, row[1:]))
            assert len(numbers) == len(columns)+1 and all(map(math.isfinite, numbers))
            times.append(numbers[0])
            for series, value in zip(values, numbers[1:]):
                series.append(value)
            remaining()
    assert terminal and times[0] == 0 and times[-1] >= 34e-9-1e-15
    assert all(a < b for a, b in zip(times, times[1:]))
    records = []
    for position, case_index in enumerate(selected):
        incoming, outgoing = values[2*position:2*position+2]
        case, reference = plan['fixtures'][case_index], base['records'][case_index]
        assert reference['case_index'] == case_index
        record = dict(case_index=case_index, output_min_v=min(outgoing), output_max_v=max(outgoing))
        assert min(outgoing) < .18 and max(outgoing) > 1.62
        changes = []
        for rising in (False, True):
            starts = crossings(times, incoming, .9, rising)
            ends = crossings(times, outgoing, .9, rising != case['inverted'])
            assert len(starts) == len(ends) == 2
            delays = [(b-a)*1e9 for a, b in zip(starts, ends)]
            key = 'input_rise_delay_ns' if rising else 'input_fall_delay_ns'
            record[key] = delays
            delta = [(a-b)*1000 for a, b in zip(delays, reference[key])]
            record[key.replace('_ns', '_change_ps')] = delta
            changes.extend(delta)
        record['maximum_absolute_delay_change_ps'] = max(map(abs, changes))
        record['output_crossings_ns'] = {
            f'{"rise" if rising else "fall"}_{level}':
                [t*1e9 for t in crossings(times, outgoing, level, rising)]
            for rising in (False, True) for level in (.36, .9, 1.44)}
        records.append(record)
    for path, digest in pins.items():
        assert sha(Path(path)) == digest, path
    remaining()
    # Runtime status changes after publication; exclude it from pinned artifacts.
    artifacts = {str(p): sha(p) for p in out.iterdir() if p.is_file() and p.name != 'status.json'}
    save(out/'assessment.json', dict(input_sha256=pins, artifacts=artifacts, records=records,
        fixtures=len(records), all_native_waveform_events_terminal=True, pvt=plan['pvt'],
        native_jobs_added=1, numerical_domain_enclosure_qualified=False,
        physical_timing_qualified=False, release_qualified=False, scope=__doc__))
    status('terminal_assessment', fixtures=len(records))
    print(f'Numerical refinement measured {len(records)} fixtures', flush=True)


if __name__ == '__main__':
    main()
