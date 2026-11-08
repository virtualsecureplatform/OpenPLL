"""Inventory per-register reset and pulse checks under retained screening constraints."""
import argparse
import json
import math
import os
from pathlib import Path
import re
import time
from common_v3 import ROOT, save, sha, verify
from resources import identity, lease
from compiled_charge_v2 import execute
from screen_prototype_decision_hold_phase_v5 import OPENROAD


def slacks(text):
    rows = []
    for value, state in re.findall(r'([-+0-9.eE]+)\s+slack \((MET|VIOLATED)\)', text):
        value = float(value)
        if not math.isfinite(value) or (value >= 0) != (state == 'MET'):
            raise ValueError('inconsistent finite native slack')
        rows.append(value)
    return rows


def section(text, tag):
    begin, end = tag + '_BEGIN', tag + '_END'
    if text.count(begin) != 1 or text.count(end) != 1:
        raise ValueError('unique completed endpoint query markers required')
    return text.split(begin)[1].split(end)[0]


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    os.sched_setaffinity(0, {17})
    os.environ.update(OMP_NUM_THREADS='1', OMP_THREAD_LIMIT='1', OPENBLAS_NUM_THREADS='1')
    save(output / 'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid())) )
    base = ROOT / 'build/signoff400'
    route = base / 'prototype_v3_selected_route_019/assessment.json'
    try:
        r = json.loads(route.read_text())
        verify(r['candidate_source_sha256'])
        expected = sum(count for master, count in r['cell_inventory'].items()
                       if re.fullmatch(r'sky130_fd_sc_hs__df[rs]tp_[124]', master))
        if expected != 481:
            raise ValueError('retained sequential inventory differs')
        pins = {str(p): sha(p) for p in (route, Path(__file__).resolve(), Path(OPENROAD))}
        artifacts, rows = {}, []
        previous_reset, previous_clock = None, None
        for corner in ('tt', 'ff', 'ss', 'sf', 'fs'):
            baseline = base / f'prototype_v3_selected_402p1_phase_{corner}_019'
            receipt = baseline / 'assessment.json'
            a = json.loads(receipt.read_text())
            verify(a['input_sha256'])
            verify(a['artifacts'])
            original = baseline / 'screen.tcl'
            prefix = original.read_text().split('report_parasitic_annotation')[0]
            for line in prefix.splitlines():
                if line.startswith(('read_liberty ', 'read_db ', 'source ', 'read_spef ')):
                    p = Path(line.split()[-1])
                    pins[str(p)] = sha(p)
            pins.update({str(p): sha(p) for p in (receipt, original)})
            directory = output / corner
            directory.mkdir()
            script = directory / 'checks.tcl'
            script.write_text(prefix + f'''
set resets [all_registers -async_pins]
set clocks [all_registers -clock_pins]
if {{[llength $resets] != {expected} || [llength $clocks] != {expected}}} {{error "sequential pin inventory mismatch"}}
set index 0
foreach pin $resets {{
 puts "OPENPLL_RESET_PIN $index [get_full_name $pin]"
 foreach {{type delay}} {{recovery max removal min}} {{
  puts "OPENPLL_RESET_${{index}}_${{type}}_BEGIN"
  report_checks -to [list $pin] -path_delay $delay -group_path_count 1 -endpoint_path_count 1 -digits 9
  puts "OPENPLL_RESET_${{index}}_${{type}}_END"
 }}
 incr index
}}
array set reset_keys {{}}
set corner [sta::parse_corner_or_all reset_keys]
set index 0
foreach pin $clocks {{
 puts "OPENPLL_CLOCK_PIN $index [get_full_name $pin]"
 puts "OPENPLL_PULSE_${{index}}_BEGIN"
 sta::report_mpw_checks [sta::min_pulse_width_check_pins [list $pin] $corner] 1
 puts "OPENPLL_PULSE_${{index}}_END"
 incr index
}}
exit
''')
            pins[str(script)] = sha(script)
            save(output / 'inputs.json', dict(input_sha256=pins, CPU=17, memory_GiB=4,
                 expected_registers=expected, native_limit_s_per_corner=3600,
                 inherited_reset_and_async_exceptions=True, release_ready=False))
            save(output / 'status.json', dict(state='measuring_each_register_reset_and_pulse_endpoint', corner=corner, release_ready=False))
            log = directory / 'native.log'
            with lease(1, 4, time.clock_gettime(time.CLOCK_BOOTTIME) + 86400):
                execute([OPENROAD, '-no_init', '-exit', script], log,
                        time.clock_gettime(time.CLOCK_BOOTTIME) + 3600, 4)
            text = log.read_text()
            if re.search(r'\[ERROR|Error:|STA-(1648|1650)', text):
                raise ValueError('native endpoint query failed')
            reset_pins = re.findall(r'^OPENPLL_RESET_PIN (\d+) (\S+)$', text, re.M)
            clock_pins = re.findall(r'^OPENPLL_CLOCK_PIN (\d+) (\S+)$', text, re.M)
            if any(len(pins_) != expected or [int(i) for i, _ in pins_] != list(range(expected))
                   or len({name for _, name in pins_}) != expected for pins_ in (reset_pins, clock_pins)):
                raise ValueError('complete unique native pin inventory required')
            reset_names, clock_names = [sorted(name for _, name in values) for values in (reset_pins, clock_pins)]
            if (previous_reset is not None and previous_reset != reset_names
                    or previous_clock is not None and previous_clock != clock_names):
                raise ValueError('endpoint inventory changed across cell-view corners')
            previous_reset, previous_clock = reset_names, clock_names
            for index, pin in reset_pins:
                for kind in ('recovery', 'removal'):
                    block = section(text, f'OPENPLL_RESET_{index}_{kind}')
                    values = slacks(block)
                    if len(values) > 1 or (values and f'({kind} check against ' not in block):
                        raise ValueError('unexpected reset path type or multiplicity')
                    if not values and 'No paths found.' not in block:
                        raise ValueError('missing explicit native no-path result')
                    rows.append(dict(corner=corner, pin=pin, check=kind, reported=bool(values),
                                     slack_ns=values[0] if values else None,
                                     passed=values[0] >= 0 if values else None,
                                     no_path_is_not_a_pass=not values))
            for index, pin in clock_pins:
                block = section(text, f'OPENPLL_PULSE_{index}')
                checks = block.split('Pin: ')[1:]
                for check in checks:
                    values = slacks(check)
                    width = re.findall(r'required pulse width \((high|low)\)', check)
                    if len(values) != 1 or len(width) != 1 or check.splitlines()[0].strip() != pin:
                        raise ValueError('bound pulse pin, polarity and one slack required')
                    rows.append(dict(corner=corner, pin=pin, check='pulse_' + width[0],
                                     reported=True, slack_ns=values[0], passed=values[0] >= 0))
                if not checks:
                    rows.append(dict(corner=corner, pin=pin, check='pulse_unreported', reported=False,
                                     slack_ns=None, passed=None))
            artifacts[str(log)] = sha(log)
            verify(pins)
        detail = output / 'endpoints.json'
        save(detail, rows)
        artifacts[str(detail)] = sha(detail)
        counts = {kind: dict(queried=sum(row['check'] == kind for row in rows),
                            reported=sum(row['check'] == kind and row['reported'] for row in rows),
                            violated=sum(row['check'] == kind and row['passed'] is False for row in rows))
                  for kind in ('recovery', 'removal', 'pulse_high', 'pulse_low', 'pulse_unreported')}
        save(output / 'assessment.json', dict(input_sha256=pins, artifacts=artifacts,
             registers_per_corner=expected, native_corner_inventories_identical=True, counts=counts,
             all_reported_checks_pass=all(row['passed'] is True for row in rows if row['reported']),
             all_async_endpoints_have_reported_checks=all(row['reported'] for row in rows if row['check'] in ('recovery', 'removal')),
             all_clock_endpoints_have_high_low_checks=all(any(row['corner'] == corner and row['pin'] == pin
                 and row['check'] == kind for row in rows) for corner in ('tt', 'ff', 'ss', 'sf', 'fs')
                 for pin in previous_clock for kind in ('pulse_high', 'pulse_low')),
             no_new_timing_exceptions=True, inherited_primary_reset_and_async_exceptions=True,
             missing_path_classification_qualified=False, actual_startup_frequency_range_qualified=False,
             cell_models_qualified=False, full_mode_reset_timing_qualified=False, release_ready=False))
        save(output / 'status.json', dict(state='per_register_reset_and_pulse_coverage_measured', release_ready=False))
    except BaseException as error:
        save(output / 'status.json', dict(state='stopped_without_qualification', reason=repr(error), release_ready=False))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output.resolve())
