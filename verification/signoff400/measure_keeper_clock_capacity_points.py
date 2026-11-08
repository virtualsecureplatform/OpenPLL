"""Measure 400/420 MHz ECO capacity using retained screening exceptions and cell views."""
import argparse
import json
import os
from pathlib import Path
import re
import time
from common_v3 import ROOT, save, sha, verify
from resources import identity, lease
from compiled_charge_v2 import execute
from screen_prototype_decision_hold_phase_v5 import OPENROAD


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    os.sched_setaffinity(0, {30})
    os.environ.update(OMP_NUM_THREADS='1', OMP_THREAD_LIMIT='1', OPENBLAS_NUM_THREADS='1')
    save(output / 'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid())) )
    base = ROOT / 'build/signoff400/selected_keeper_clock_branch_timing_1454'
    try:
        receipt = base / 'assessment.json'
        a = json.loads(receipt.read_text())
        verify(a['input_sha256'])
        verify(a['artifacts'])
        pins = {str(p): sha(p) for p in (receipt, Path(__file__).resolve(), Path(OPENROAD))}
        rows, artifacts = [], {}
        for corner in ('tt', 'ff', 'ss', 'sf', 'fs'):
            original = base / corner / 'paths.tcl'
            prefix = original.read_text().split('report_parasitic_annotation')[0]
            reads = [line.split()[-1] for line in prefix.splitlines()
                     if line.startswith(('read_liberty ', 'read_db ', 'read_spef ', 'source '))]
            pins.update({str(p): sha(p) for p in [original, *map(Path, reads)]})
            sdcs = [Path(line.split()[-1]) for line in prefix.splitlines() if line.startswith('source ')]
            if len(sdcs) != 1:
                raise ValueError('one retained constraint file required')
            sdc = sdcs[0]
            for mhz in (400, 420):
                directory = output / f'{corner}_{mhz}'
                directory.mkdir()
                constraints = directory / 'capacity.sdc'
                text, count = re.subn(r'^(create_clock -name PLLOUT -period )\S+( \[get_ports PLLOUT\])$',
                                      lambda m: m[1] + format(1000 / mhz, '.12g') + m[2], sdc.read_text(), flags=re.M)
                if count != 1 or 'set_false_path -from [get_ports RESET_N]' not in text:
                    raise ValueError('explicit source period and retained reset screening exception required')
                text = text.replace('# 500 MHz is a capacity screen, pending measured startup/tracking bounds.',
                                    f'# {mhz} MHz capacity point; actual startup/tracking bounds remain pending.')
                constraints.write_text(text)
                script = directory / 'capacity.tcl'
                if prefix.count('source ' + str(sdc)) != 1:
                    raise ValueError('unique retained source command required')
                script.write_text(prefix.replace('source ' + str(sdc), 'source ' + str(constraints))
                    + '\nreport_worst_slack -max -digits 9\nreport_worst_slack -min -digits 9\n'
                    + 'report_checks -path_delay max -group_path_count 1 -digits 9\n'
                    + 'report_check_types -max_slew -max_capacitance -min_pulse_width -recovery -removal -violators -digits 9\nexit\n')
                pins.update({str(p): sha(p) for p in (constraints, script)})
                save(output / 'inputs.json', dict(input_sha256=pins, CPU=30, memory_GiB=4,
                     frequency_points_mhz=[400, 420], retained_reset_and_async_screening_exceptions=True,
                     cell_models_or_actual_operating_range_qualified=False, release_ready=False))
                save(output / 'status.json', dict(state='measuring_ECO_capacity_point', corner=corner, mhz=mhz, release_ready=False))
                with lease(1, 4, time.clock_gettime(time.CLOCK_BOOTTIME) + 86400):
                    execute([OPENROAD, '-no_init', '-exit', script], directory / 'native.log',
                            time.clock_gettime(time.CLOCK_BOOTTIME) + 3600, 4)
                native = (directory / 'native.log').read_text()
                if re.search(r'\[ERROR|Error:|STA-(1648|1650)', native):
                    raise ValueError('native timing query failed')
                slack = {kind: float(value) for kind, value in re.findall(r'worst slack (max|min) ([-+0-9.eE]+)', native)}
                if set(slack) != {'max', 'min'}:
                    raise ValueError('complete setup/hold screening results required')
                rows.append(dict(corner=corner, frequency_mhz=mhz, worst_slack_ns=slack,
                                 max_path_capacity_screen_pass=slack['max'] >= 0))
                artifacts[str(directory / 'native.log')] = sha(directory / 'native.log')
        verify(pins)
        if len(rows) != 10:
            raise ValueError('all five corners and both frequency points required')
        save(output / 'assessment.json', dict(input_sha256=pins, artifacts=artifacts, measured_points=rows,
             same_candidate_database_and_wire_RC=True, no_new_timing_exceptions=True,
             retained_reset_and_async_screening_exceptions=True, historical_conditional_cell_views=True,
             parent_fill_aware_parasitics_used=False, startup_reset_timing_qualified=False,
             actual_operating_range_qualified=False, physical_timing_qualified=False, release_ready=False))
        save(output / 'status.json', dict(state='clock_capacity_points_measured_unqualified', release_ready=False))
    except BaseException as error:
        save(output / 'status.json', dict(state='stopped_without_qualification', reason=repr(error), release_ready=False))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output.resolve())
