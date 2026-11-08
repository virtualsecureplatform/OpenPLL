"""Compare original-macro STA reset slews and Q loads to the declared pulse grid."""
import argparse
import json
import math
import os
from pathlib import Path
import re
import time

from common_v3 import ROOT, save, sha, verify
from compiled_charge_v2 import execute
from inventory_selected_pin_electrical_coverage_v2 import native_script, table_rows
from resources import identity, lease
from screen_prototype_decision_hold_phase_v5 import OPENROAD


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    os.sched_setaffinity(0, {18})
    os.environ.update(OMP_NUM_THREADS='1', OMP_THREAD_LIMIT='1')
    save(output / 'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid())) )
    base = ROOT / 'build/signoff400'
    plan = base / 'selected_keeper_reset_pulse_grid_1504/plan.json'
    try:
        grid = json.loads(plan.read_text())
        loads = {}
        for case in grid['cases']:
            if case['master'] in loads and loads[case['master']] != case['load_fF']:
                raise ValueError('one declared load per master required')
            loads[case['master']] = case['load_fF']
        slew_range_ns = [min(c['full_ramp_ps'] for c in grid['cases']) * .6 / 1000,
                         max(c['full_ramp_ps'] for c in grid['cases']) * .6 / 1000]
        helpers = ['inventory_selected_pin_electrical_coverage_v2.py',
                   'report_selected_electrical_margins_v2.py']
        pins = {str(p): sha(p) for p in [plan, Path(__file__).resolve(), Path(OPENROAD),
                *[Path(__file__).with_name(n) for n in helpers]]}
        results, artifacts = {}, {}
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
            pins.update({str(p): sha(p) for p in [receipt, original]})
            target = output / corner
            target.mkdir()
            table, script, log = [target / n for n in ('pins.tsv', 'query.tcl', 'native.log')]
            script.write_text(native_script(prefix, table))
            pins[str(script)] = sha(script)
            save(output / 'status.json', dict(state='measuring_routed_reset_fixture_envelope', corner=corner, release_ready=False))
            with lease(1, 4, time.clock_gettime(time.CLOCK_BOOTTIME) + 86400):
                execute([OPENROAD, '-no_init', '-exit', script], log,
                        time.clock_gettime(time.CLOCK_BOOTTIME) + 3600, 4)
            if re.search(r'\[ERROR|Error:|STA-(1648|1650)', log.read_text()):
                raise ValueError('native pin inventory failed')
            rows = table_rows(table)
            resets = [r for r in rows if r['kind'] == 'cell' and r['master'] in loads
                      and r['port'] in ('RESET_B', 'SET_B')]
            outputs = [r for r in rows if r['kind'] == 'cell' and r['master'] in loads and r['port'] == 'Q']
            if len(resets) != 481 or len(outputs) != 481:
                raise ValueError('all 481 reset pins and corresponding Q pins required')
            values = [r[f] for r in resets for f in ('rise_min_ns','rise_max_ns','fall_min_ns','fall_max_ns')]
            if any(v is None or not math.isfinite(v) or v < 0 for v in values):
                raise ValueError('finite nonnegative reset slew required')
            load_margins = []
            for row in outputs:
                cap = row['cap_max_pf']
                if cap is None or not math.isfinite(cap) or cap < 0:
                    raise ValueError('finite connected Q load required')
                load_margins.append(dict(pin=row['pin'], master=row['master'],
                    modeled_load_fF=cap*1000, fixture_load_fF=loads[row['master']],
                    margin_fF=loads[row['master']]-cap*1000))
            results[corner] = dict(reset_pins=len(resets), Q_pins=len(outputs),
                reset_slew_range_ns=[min(values), max(values)],
                zero_slew_values=sum(v == 0 for v in values),
                slew_values_outside_grid=sum(not slew_range_ns[0] <= v <= slew_range_ns[1] for v in values),
                load_exceedances=sum(r['margin_fF'] < 0 for r in load_margins),
                worst_Q_load_margin=min(load_margins, key=lambda r:r['margin_fF']))
            detail = target / 'sequential_pins.json'
            save(detail, dict(reset_pins=resets, Q_loads=load_margins))
            artifacts.update({str(p): sha(p) for p in [table, log, detail]})
        verify(pins)
        save(output / 'assessment.json', dict(input_sha256=pins, artifacts=artifacts,
             corners=results, fixture_slew_range_20_to_80_ns=slew_range_ns,
             actual_routed_geometry='original_macro_019',
             periodic_screening_constraints_only=True, sampled_cell_views_only=True,
             discrete_grid_is_not_continuous_bound=True,
             actual_reset_slew_and_load_envelope_qualified=False,
             external_reset_waveform_qualified=False, physical_reset_timing_qualified=False,
             release_ready=False))
        save(output / 'status.json', dict(state='routed_reset_fixture_envelope_measured', release_ready=False))
    except BaseException as error:
        save(output / 'status.json', dict(state='stopped_without_qualification', reason=repr(error), release_ready=False))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    run(parser.parse_args().output.resolve())
