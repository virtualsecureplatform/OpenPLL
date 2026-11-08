"""Measure native reset-pin pulse-check coverage without treating silence as pass."""
import argparse
import json
import os
from pathlib import Path
import re
import time

from common_v3 import ROOT, save, sha, verify
from compiled_charge_v2 import execute
from measure_keeper_reset_endpoint_coverage import section, slacks
from resources import identity, lease
from screen_prototype_decision_hold_phase_v5 import OPENROAD


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    os.sched_setaffinity(0, {17})
    os.environ.update(OMP_NUM_THREADS='1', OMP_THREAD_LIMIT='1')
    save(output / 'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid())) )
    base = ROOT / 'build/signoff400'
    coverage = base / 'selected_keeper_reset_endpoint_coverage_1496/assessment.json'
    try:
        previous = json.loads(coverage.read_text())
        verify(previous['input_sha256'])
        verify(previous['artifacts'])
        pins = {str(p): sha(p) for p in [coverage, Path(__file__).resolve(), Path(OPENROAD),
                Path(__file__).with_name('measure_keeper_reset_endpoint_coverage.py')]}
        expected = previous['registers_per_corner']
        artifacts, rows = {}, []
        endpoint_sets = []
        for corner in ('tt', 'ff', 'ss', 'sf', 'fs'):
            original = base / f'prototype_v3_selected_402p1_phase_{corner}_019/screen.tcl'
            pins[str(original)] = sha(original)
            prefix = original.read_text().split('report_parasitic_annotation')[0]
            directory = output / corner
            directory.mkdir()
            script = directory / 'checks.tcl'
            script.write_text(prefix + '''
array set reset_keys {}
set corner [sta::parse_corner_or_all reset_keys]
set index 0
foreach pin [all_registers -async_pins] {
 puts "OPENPLL_ASYNC_PIN $index [get_full_name $pin]"
 puts "OPENPLL_ASYNC_${index}_BEGIN"
 sta::report_mpw_checks [sta::min_pulse_width_check_pins [list $pin] $corner] 1
 puts "OPENPLL_ASYNC_${index}_END"
 incr index
}
exit
''')
            pins[str(script)] = sha(script)
            save(output / 'status.json', dict(state='querying_native_async_reset_pulse_checks', corner=corner, release_ready=False))
            log = directory / 'native.log'
            with lease(1, 4, time.clock_gettime(time.CLOCK_BOOTTIME) + 86400):
                execute([OPENROAD, '-no_init', '-exit', script], log,
                        time.clock_gettime(time.CLOCK_BOOTTIME) + 3600, 4)
            text = log.read_text()
            if re.search(r'\[ERROR|Error:', text):
                raise ValueError('native query error')
            endpoints = re.findall(r'^OPENPLL_ASYNC_PIN (\d+) (\S+)$', text, re.M)
            if (len(endpoints) != expected or [int(i) for i, _ in endpoints] != list(range(expected))
                    or len({pin for _, pin in endpoints}) != expected):
                raise ValueError('complete unique reset-pin inventory required')
            endpoint_sets.append(sorted(pin for _, pin in endpoints))
            for index, pin in endpoints:
                block = section(text, f'OPENPLL_ASYNC_{index}')
                values = slacks(block)
                rows.append(dict(corner=corner, pin=pin, reported=bool(values),
                                 slack_ns=values, passed=all(v >= 0 for v in values) if values else None))
            artifacts[str(log)] = sha(log)
        if any(names != endpoint_sets[0] for names in endpoint_sets):
            raise ValueError('reset inventory changed between corners')
        detail = output / 'endpoints.json'
        save(detail, rows)
        artifacts[str(detail)] = sha(detail)
        verify(pins)
        save(output / 'assessment.json', dict(input_sha256=pins, artifacts=artifacts,
             async_pins_per_corner=expected, queried=len(rows),
             reported=sum(r['reported'] for r in rows),
             unreported=sum(not r['reported'] for r in rows),
             violated=sum(r['passed'] is False for r in rows),
             missing_check_is_not_a_pass=True, no_new_timing_exceptions=True,
             external_reset_pulse_width_qualified=False, physical_reset_timing_qualified=False,
             release_ready=False))
        save(output / 'status.json', dict(state='native_async_reset_pulse_coverage_measured', release_ready=False))
    except BaseException as error:
        save(output / 'status.json', dict(state='stopped_without_qualification', reason=repr(error), release_ready=False))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output.resolve())
