#!/usr/bin/env python3
"""Audit all12 saved synthetic directed changes, stimulus and reset continuity.

Requires both trace phases, matching source/artifact hashes, real divider
changes and tracking release/reacquisition. Physical qualification stays false.
"""
import argparse
import csv
import itertools
import json
from pathlib import Path

from run_dco_qualification import REQUIREMENTS, sha, save


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--diagnostic', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    base, out = args.diagnostic.resolve(), args.output.resolve()
    source = base/'assessment.json'
    report = json.loads(source.read_text())
    assert report['qualification_cases_passed'] == 0
    assert not report['dco_model_qualified'] and not report['interface_model_qualified']
    assert not report['whole_pll_qualification_pass'] and not report['release_qualified']
    spec = json.loads(REQUIREMENTS.read_text())
    expected = set(itertools.permutations(spec['modes_mhz'], 2))
    actual = {(r['from_mode_mhz'], r['to_mode_mhz']) for r in report['records']}
    assert actual == expected and len(report['records']) == 12
    pins = {str(p): sha(p) for p in (source, REQUIREMENTS, Path(__file__).resolve())}
    for group in (report['input_sha256'], *[r['artifacts'] for r in report['records']]):
        for name, digest in group.items():
            assert sha(name) == digest, name
            pins[name] = digest
    results = []
    for case in report['records']:
        old, new = case['from_mode_mhz'], case['to_mode_mhz']
        directory = base/f'{old}_to_{new}MHz'
        assert case['returncode'] == 0 and case['terminal'] and not case['failure_observed']
        assert case['initial_trace_passed'] and case['changed_trace_passed']
        assert case['external_reset_at_change'] is False and case['change_ns'] == 220100
        trace = []
        with (directory/'phase.csv').open() as stream:
            for row in csv.DictReader(stream):
                if row['event'] == 'RESET':
                    trace.append(int(row['time_ps']))
        assert trace == [0], ('unexpected oscillator reset', old, new, trace)
        with (directory/'states.csv').open() as stream:
            states = [r for r in csv.DictReader(stream)
                      if float(r['time_ns']) >= 100 and r['divider'].isdigit()]
        changes, previous = [], None
        for row in states:
            divider = int(row['divider'])
            if divider != previous:
                changes.append((float(row['time_ns']), divider))
                previous = divider
        assert [r[1] for r in changes] == [old//25, new//25]
        assert changes[1][0] == 220100
        drop = case['tracking_dropped_after_change_ns']
        recovered = case['tracking_reasserted_ns']
        assert 220100 <= drop < recovered <= 220100+spec['acquisition_limit_ns']
        for label, mode, enabled, stop in [('initial', old, 100, 220000), ('changed', new, 220100, 440000)]:
            accepted = json.loads((directory/(label+'_trace_acceptance.json')).read_text())
            assert accepted['passed'] and accepted['sustained_final_pass']
            assert accepted['complete_control_trace_checked'] and accepted['synthetic_models_only']
            assert accepted['target_mhz'] == mode and accepted['stimulus_ns'] == enabled
            assert accepted['observation_stop_ns'] == stop
            assert not accepted['release_qualified'] and not accepted['whole_pll_qualification_pass']
            assert accepted['acquisition_confirmed_ns']-enabled <= spec['acquisition_limit_ns']
            assert len(accepted['windows']) >= spec['sustained_windows']
            assert all(w['passed'] for w in accepted['windows'][-spec['sustained_windows']:])
        audited = case['clock_delivery_audit']
        assert audited['decimal_phase_conservation_passed'] and audited['output_rising_edges_matched'] > 0
        results.append(dict(from_mode_mhz=old, to_mode_mhz=new,
            reset_events_ps=trace, actual_divider_transition_ns=changes[1][0],
            tracking_drop_delay_ns=drop-220100, tracking_reacquisition_ns=recovered-220100,
            both_trace_phases_passed=True, physical_qualification_pass=False))
    out.mkdir(parents=True, exist_ok=False)
    save(out/'assessment.json', dict(input_sha256=pins, records=results,
        all12_synthetic_directed_changes_audited=True, additional_reset_at_mode_change=False,
        native_jobs_added=0, qualification_cases_passed=0, release_gains_selected=False,
        whole_pll_qualification_pass=False, release_qualified=False, scope=__doc__))
    print('Audited all12 synthetic changes, both trace phases and no reset at the mode change')


if __name__ == '__main__':
    main()
