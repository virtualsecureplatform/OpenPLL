#!/usr/bin/env python3
"""Exercise the frozen candidate in a synthetic continuous-phase closed loop.

Every frequency, detector decision and detector timing assumption is synthetic.
This brings up a driver; it must never count as a physical or release case.
"""
import argparse
import csv
import json
from pathlib import Path
import subprocess
import time

from prepare_functional_matrix import FROZEN, FILES
from run_dco_qualification import ROOT, REQUIREMENTS, sha, save


def main():
    started = time.monotonic()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    here = Path(__file__).resolve().parent
    harness = ROOT/'verification/timing450/IntegerPLL_ReleaseHarness.v'
    bench = here/'tb_frozen_closed_loop_diagnostic.v'
    inputs = [Path(__file__).resolve(), REQUIREMENTS, harness, bench,
              here/'phase_clock_vpi.cpp', here/'phase_clock.h', *[FROZEN/n for n in FILES],
              Path('/usr/bin/iverilog'), Path('/usr/bin/vvp'), Path('/usr/bin/iverilog-vpi')]
    pins = {str(p): sha(p) for p in inputs}

    def run(command, log):
        with log.open('x') as stream:
            return subprocess.run(list(map(str, command)), cwd=out, stdout=stream,
                stderr=subprocess.STDOUT, timeout=max(.001, 43200-(time.monotonic()-started))).returncode

    assert run(['/usr/bin/iverilog-vpi', here/'phase_clock_vpi.cpp'], out/'vpi_compile.log') == 0
    plugin = out/'phase_clock_vpi.vpi'
    binary = out/'closed_loop.vvp'
    assert run(['/usr/bin/iverilog', '-g2012', '-s', 'frozen_closed_loop_diagnostic', '-o', binary,
                *[FROZEN/n for n in FILES], harness, bench], out/'compile.log') == 0
    table = out/'SYNTHETIC_DO_NOT_QUALIFY.table'
    table.write_text(''.join(f'{coarse} {fine} {(500000000000-9000000000*coarse)*(2000+fine)//2000}\n'
                            for coarse in range(48) for fine in range(256)))
    for p in (plugin, binary, table):
        pins[str(p)] = sha(p)
    records = []
    for mode in (100, 250, 300, 400):
        directory = out/f'{mode}MHz'
        directory.mkdir()
        phase, edges, states = (directory/name for name in ('phase.csv', 'edges.csv', 'states.csv'))
        code = run(['/usr/bin/vvp', '-M', out, '-m', 'phase_clock_vpi', binary,
                    f'+phase400_table={table}', f'+phase400_trace={phase}', f'+divider={mode//25}',
                    f'+edge_trace={edges}', f'+state_trace={states}'], directory/'run.log')
        log = (directory/'run.log').read_text()
        record = dict(mode_mhz=mode, returncode=code, terminal='SYNTHETIC_CLOSED_LOOP_END' in log,
                      physical_models_qualified=False, qualification_case_pass=False)
        if states.exists():
            with states.open() as stream:
                rows = list(csv.DictReader(stream))
            numeric = [r for r in rows if all(r[k].isdigit() for k in ('coarse', 'fine', 'tracking', 'failed'))]
            tracking = [float(r['time_ns']) for r in numeric if r['tracking'] == '1']
            record.update(first_tracking_ns=min(tracking) if tracking else None,
                          failure_observed=any(r['failed'] == '1' for r in numeric),
                          final_state=numeric[-1] if numeric else None)
        record['artifacts'] = {str(p): sha(p) for p in directory.iterdir() if p.is_file()}
        records.append(record)
    for p, digest in pins.items():
        assert sha(p) == digest, p
    save(out/'assessment.json', dict(input_sha256=pins, records=records,
        complete_synthetic_grid_rows=48*256, qualification_cases_passed=0,
        whole_pll_qualification_pass=False, release_qualified=False,
        dco_model_qualified=False, interface_model_qualified=False,
        scope=__doc__))
    print(json.dumps(records, indent=2))


if __name__ == '__main__':
    main()
