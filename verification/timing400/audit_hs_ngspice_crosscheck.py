#!/usr/bin/env python3
"""Independently remeasure the two NAND references and the sampled envelope.

Uses Decimal interpolation of saved native waveforms. A two-run one-case
comparison cannot qualify a numerical/model domain, full envelope or release.
"""
import argparse
from decimal import Decimal, localcontext
import json
from pathlib import Path

from run_dco_qualification import ROOT, sha, save


def delays(path):
    samples = []
    with path.open() as stream:
        assert stream.readline().lower().split() == ['time', 'v(in)', 'v(out)']
        for line in stream:
            row = list(map(Decimal, line.split()))
            assert len(row) == 3 and all(v.is_finite() for v in row)
            assert not samples or samples[-1][0] < row[0]
            samples.append(row)
    assert samples[0][0] == 0 and samples[-1][0] >= Decimal('5e-9')

    def crossings(column, rising):
        result = []
        for a, b in zip(samples, samples[1:]):
            if (a[column] < Decimal('.9') <= b[column]) if rising else (a[column] > Decimal('.9') >= b[column]):
                result.append(a[0]+(b[0]-a[0])*(Decimal('.9')-a[column])/(b[column]-a[column]))
        return result

    result = {}
    for rising in (False, True):
        incoming = [t for t in crossings(1, rising) if Decimal('.4e-9') < t < Decimal('4e-9')]
        outgoing = crossings(2, not rising)
        assert len(incoming) == 2
        matched = []
        for t in incoming:
            selected = [u for u in outgoing if t < u < t+Decimal('.8e-9')]
            assert len(selected) == 1
            matched.append((selected[0]-t)*Decimal('1e9'))
        result['input_rise_delay_ns' if rising else 'input_fall_delay_ns'] = sum(matched)/2
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    out = args.output.resolve()
    base = ROOT/'build/timing400/release_001'
    coverage_path = base/'hs_timing_coverage_001.json'
    coverage = json.loads(coverage_path.read_text())
    pins = {str(p): sha(p) for p in (coverage_path, Path(__file__).resolve())}
    records, measured = [], []
    with localcontext() as context:
        context.prec = 40
        for name in ('hs_ngspice_crosscheck_001', 'hs_ngspice_crosscheck_refined_001'):
            directory = base/name
            source = directory/'assessment.json'
            report = json.loads(source.read_text())
            assert not report['release_qualified'] and not report['timing_envelope_adopted']
            pins[str(source)] = sha(source)
            for group in (report['input_sha256'], report['artifacts']):
                for path, digest in group.items():
                    assert sha(path) == digest, path
                    pins[path] = digest
            assert str(directory/'waveform.dat') in report['artifacts']
            guard = json.loads((directory/'slot_guard.json').read_text())
            assert guard['dispatch_resumed'] and guard['native_children_paused'] is False
            assert guard['maximum_combined_native_count_observed'] <= 4 and guard['reference_exit_code'] == 0
            d = delays(directory/'waveform.dat')
            measured.append(d)
            comparisons = []
            for key, value in d.items():
                assert abs(float(value)-report['ngspice_delays_ns'][key]) < 1e-12
                kind = 'cell_rise' if key == 'input_fall_delay_ns' else 'cell_fall'
                bound, = [c for c in coverage['comparisons'] if c['case'] == report['source_case'] and c['kind'] == kind]
                fast, slow = Decimal(str(bound['fast_ns'])), Decimal(str(bound['slow_ns']))
                comparisons.append(dict(kind=kind, independent_native_delay_ns=str(value),
                    sampled_fast_bound_ns=str(fast), sampled_slow_bound_ns=str(slow),
                    enclosed=fast <= value <= slow,
                    below_fast_ps=str(max(Decimal(0), fast-value)*1000)))
            records.append(dict(directory=str(directory), comparisons=comparisons))
        differences = {k: str((measured[1][k]-measured[0][k])*1000) for k in measured[0]}
    out.mkdir(parents=True, exist_ok=False)
    save(out/'assessment.json', dict(input_sha256=pins, records=records,
        refined_minus_original_ngspice_ps=differences, independent_decimal_delay_checks=4,
        one_case_only=True, model_version_or_numerical_cause_resolved=False,
        numerical_domain_enclosure_qualified=False, timing_envelope_adopted=False,
        physical_timing_qualified=False, release_qualified=False, scope=__doc__))
    print(json.dumps(dict(records=records, refined_minus_original_ngspice_ps=differences), indent=2))


if __name__ == '__main__':
    main()
