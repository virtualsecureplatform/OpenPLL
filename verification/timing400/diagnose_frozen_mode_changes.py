#!/usr/bin/env python3
"""Exercise all12 directed mode changes using explicitly synthetic models.

Uses the previously tested KI1/KP4 synthetic grid and frozen candidate RTL.
Validates driver sequence/clock delivery, not physical behavior or PVT coverage.
"""
import argparse
import csv
from decimal import Decimal
import itertools
import json
from pathlib import Path
import subprocess
import time

from audit_closed_loop_driver import audit_trace
from functional_acceptance import evaluate
from prepare_functional_matrix import FROZEN, FILES
from run_dco_qualification import ROOT, REQUIREMENTS, sha, save


def main():
    deadline = time.monotonic()+43200
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    here = Path(__file__).resolve().parent
    harness = ROOT/'verification/timing450/IntegerPLL_ReleaseHarness.v'
    bench = here/'tb_frozen_mode_change_diagnostic.v'
    control = ROOT/'build/timing400/release_001/frozen_closed_loop_diagnostic_ki1_kp4_001'
    source = control/'assessment.json'
    previous = json.loads(source.read_text())
    assert previous['diagnostic_ki'] == 1 and previous['diagnostic_kp'] == 4
    assert previous['qualification_cases_passed'] == 0 and not previous['release_qualified']
    source_table = control/'SYNTHETIC_DO_NOT_QUALIFY.table'
    assert sha(source_table) == previous['input_sha256'][str(source_table)]
    inputs = [Path(__file__).resolve(), REQUIREMENTS, harness, bench, source, source_table,
              here/'phase_clock_vpi.cpp', here/'phase_clock.h', here/'functional_acceptance.py',
              here/'audit_closed_loop_driver.py', *[FROZEN/n for n in FILES],
              Path('/usr/bin/iverilog'), Path('/usr/bin/vvp'), Path('/usr/bin/iverilog-vpi')]
    pins = {str(p): sha(p) for p in inputs}
    spec = json.loads(REQUIREMENTS.read_text())

    def run(command, log):
        remaining = deadline-time.monotonic()
        assert remaining > 0, 'total12h diagnostic budget exhausted'
        with log.open('x') as stream:
            return subprocess.run(list(map(str, command)), cwd=out, stdout=stream,
                stderr=subprocess.STDOUT, timeout=remaining).returncode

    assert run(['/usr/bin/iverilog-vpi', here/'phase_clock_vpi.cpp'], out/'vpi_compile.log') == 0
    plugin, binary = out/'phase_clock_vpi.vpi', out/'mode_changes.vvp'
    assert run(['/usr/bin/iverilog', '-g2012', '-s', 'frozen_mode_change_diagnostic', '-o', binary,
                *[FROZEN/n for n in FILES], harness, bench], out/'compile.log') == 0
    table = out/'SYNTHETIC_DO_NOT_QUALIFY.table'
    table.write_bytes(source_table.read_bytes())
    lookup = {}
    for line in table.read_text().splitlines():
        coarse, fine, frequency = map(int, line.split())
        assert (coarse, fine) not in lookup and frequency > 0
        lookup[coarse, fine] = frequency
    for p in (plugin, binary, table):
        pins[str(p)] = sha(p)
    results = []
    for old, new in itertools.permutations(spec['modes_mhz'], 2):
        directory = out/f'{old}_to_{new}MHz'
        directory.mkdir()
        phase, edges, states = (directory/n for n in ('phase.csv', 'edges.csv', 'states.csv'))
        code = run(['/usr/bin/vvp', '-M', out, '-m', 'phase_clock_vpi', binary,
                    f'+phase400_table={table}', f'+phase400_trace={phase}', f'+divider={old//25}',
                    f'+next_divider={new//25}', f'+edge_trace={edges}', f'+state_trace={states}',
                    '+gain_ki=1', '+gain_kp=4'], directory/'run.log')
        log = (directory/'run.log').read_text()
        record = dict(from_mode_mhz=old, to_mode_mhz=new, returncode=code,
                      terminal='SYNTHETIC_MODE_CHANGE_END' in log,
                      change_ns=220100, external_reset_at_change=False,
                      qualification_case_pass=False)
        if code == 0 and record['terminal']:
            events = {k: [] for k in ('REF', 'DIV', 'OUT')}
            delivered = []
            with edges.open() as stream:
                for row in csv.DictReader(stream):
                    events[row['event']].append([float(row['time_ns']), int(row['code']), int(row['bbpd'])])
                    if row['event'] == 'OUT':
                        delivered.append(int(Decimal(row['time_ns'])*1000))
            controls = []
            with phase.open() as stream:
                for row in csv.DictReader(stream):
                    if row['event'] == 'TUNE':
                        controls.append([int(row['time_ps'])/1000, int(row['fine'])])
            for label, mode, enabled, stop in [('initial', old, 100, 220000), ('changed', new, 220100, 440000)]:
                accepted = evaluate(events, controls, mode, enabled, stop, spec)
                accepted.update(whole_pll_qualification_pass=False, synthetic_models_only=True)
                save(directory/(label+'_trace_acceptance.json'), accepted)
                record[label+'_trace_passed'] = accepted['passed']
            rises, audited = audit_trace(phase, lookup)
            assert rises == delivered
            record['clock_delivery_audit'] = dict(audited, output_rising_edges_matched=len(rises))
            with states.open() as stream:
                rows = [r for r in csv.DictReader(stream)
                        if all(r[k].isdigit() for k in ('divider', 'tracking', 'busy', 'failed'))]
            assert all(int(r['divider']) == (old//25 if float(r['time_ns']) < 220100 else new//25)
                       for r in rows if float(r['time_ns']) >= 100)
            dropped = [float(r['time_ns']) for r in rows if float(r['time_ns']) >= 220100 and r['tracking'] == '0']
            recovered = [float(r['time_ns']) for r in rows if dropped and float(r['time_ns']) > min(dropped) and r['tracking'] == '1']
            record.update(mode_stimulus_trace_verified=True,
                tracking_dropped_after_change_ns=min(dropped) if dropped else None,
                tracking_reasserted_ns=min(recovered) if recovered else None,
                failure_observed=any(r['failed'] == '1' for r in rows))
        record['artifacts'] = {str(p): sha(p) for p in directory.iterdir() if p.is_file()}
        results.append(record)
        save(out/'status.json', dict(completed_synthetic_cases=len(results), requested_synthetic_cases=12,
                                    qualification_cases_passed=0, release_qualified=False))
        print(f'{old}->{new}MHz: initial={record.get("initial_trace_passed")} changed={record.get("changed_trace_passed")}', flush=True)
    for p, digest in pins.items():
        assert sha(p) == digest, p
    save(out/'assessment.json', dict(input_sha256=pins, records=results,
        requested_synthetic_cases=12, completed_synthetic_cases=len(results),
        synthetic_cases_passing_both_phases=sum(r.get('initial_trace_passed', False) and r.get('changed_trace_passed', False) for r in results),
        diagnostic_ki=1, diagnostic_kp=4, qualification_cases_passed=0,
        dco_model_qualified=False, interface_model_qualified=False,
        whole_pll_qualification_pass=False, release_qualified=False, scope=__doc__))


if __name__ == '__main__':
    main()
