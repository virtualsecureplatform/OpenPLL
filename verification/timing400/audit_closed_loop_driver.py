#!/usr/bin/env python3
"""Check saved synthetic closed-loop phase conservation and output-edge identity.

This independent Decimal audit validates clock delivery under RTL tuning.
It does not validate the synthetic detector or any physical model or release.
"""
import argparse
import csv
from decimal import Decimal, localcontext
import json
from pathlib import Path

from run_dco_qualification import sha, save


def audit_trace(path, table):
    observed_rises = []
    with localcontext() as context:
        context.prec = 60
        denominator = Decimal(10**15)
        phase, frequency, last, count, level = Decimal(0), 0, 0, 0, 1
        last_edge, tunings, edges = -1, 0, 0
        with path.open() as stream:
            for row in csv.DictReader(stream):
                now = int(row['time_ps'])
                assert now >= last
                phase += Decimal((now-last)*frequency)/denominator
                last = now
                observed_level, measured_frequency = int(row['level']), int(row['frequency_millihz'])
                if row['event'] == 'RESET':
                    assert observed_level == 1 and measured_frequency == 0
                    phase, frequency, count, level = Decimal(0), 0, 0, 1
                elif row['event'] == 'TUNE':
                    frequency = table[int(row['coarse']), int(row['fine'])]
                    assert frequency == measured_frequency and observed_level == level
                    tunings += 1
                elif row['event'] == 'EDGE':
                    assert now > last_edge and frequency == measured_frequency and frequency > 0
                    count += 1
                    edges += 1
                    level = 1-level
                    assert observed_level == level
                    residual = phase-Decimal(count)/2
                    assert Decimal(0) <= residual < Decimal(frequency)/denominator, (now, residual)
                    if level:
                        observed_rises.append(now)
                    last_edge = now
                else:
                    raise AssertionError('Unknown phase event '+row['event'])
    assert tunings > 0 and edges > 0
    return observed_rises, dict(edges=edges, tuning_events=tunings,
                               decimal_phase_conservation_passed=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--diagnostic', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    base, out = args.diagnostic.resolve(), args.output.resolve()
    source = base/'assessment.json'
    report = json.loads(source.read_text())
    assert report['qualification_cases_passed'] == 0 and not report['release_qualified']
    assert not report['dco_model_qualified'] and not report['interface_model_qualified']
    pins = {str(source): sha(source), str(Path(__file__).resolve()): sha(Path(__file__).resolve())}
    for group in (report['input_sha256'], *[r['artifacts'] for r in report['records']]):
        for name, digest in group.items():
            assert sha(name) == digest, name
            pins[name] = digest
    table = {}
    for line in (base/'SYNTHETIC_DO_NOT_QUALIFY.table').read_text().splitlines():
        coarse, fine, frequency = map(int, line.split())
        assert (coarse, fine) not in table and frequency > 0
        table[coarse, fine] = frequency
    results = []
    for case in report['records']:
        assert case['returncode'] == 0 and case['terminal']
        directory = base/f'{case["mode_mhz"]}MHz'
        phase_rises, result = audit_trace(directory/'phase.csv', table)
        with (directory/'edges.csv').open() as stream:
            delivered = [int(Decimal(r['time_ns'])*1000) for r in csv.DictReader(stream) if r['event'] == 'OUT']
        assert phase_rises == delivered
        result.update(mode_mhz=case['mode_mhz'], delivered_output_rises=len(delivered),
                      output_edge_identity_passed=True)
        results.append(result)
    assert {r['mode_mhz'] for r in results} == {100, 250, 300, 400}
    out.mkdir(parents=True, exist_ok=False)
    save(out/'assessment.json', dict(input_sha256=pins, records=results,
        synthetic_driver_phase_audit_passed=True, detector_model_validated=False,
        qualification_cases_passed=0, whole_pll_qualification_pass=False,
        release_qualified=False, scope=__doc__))
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
