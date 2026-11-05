#!/usr/bin/env python3
"""Independent controls for selected settling-sensitive fixtures, not a library."""
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from characterize_compact_propagation import SUPPLIES
from compile_local_C_operators_v2 import digest, save


def main():
    root = Path(__file__).resolve().parents[2]
    base = root / 'build/timing400/release_001'
    shared_owner = base / 'compact_nominal_15PVT_completion_001/owner.json'
    deadline = json.loads(shared_owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    out = base / 'selected_compact_numerical_holdouts_sf_m40_001'
    out.mkdir(exist_ok=False)
    save(out / 'owner.json', dict(runner_pid=os.getpid(),
        started_utc=datetime.now(timezone.utc).isoformat(), deadline_uptime=deadline,
        inherited_shared_owner=str(shared_owner), budget_restarted=False,
        maximum_case_workers=1, maximum_total_native_workers=4,
        automatic_identical_retry=False))
    source = base / 'compact_nominal_15PVT_completion_001/sf_m40'
    original_plan = json.loads((source / 'plan.json').read_text())
    receipt = json.loads((source / 'run_001/assessment.json').read_text())
    assert receipt['passing'] == receipt['fixtures'] == 891
    assert receipt['all_native_waveform_events_terminal']
    selected = [87, 839, 874, 875]
    cases = [deepcopy(original_plan['fixtures'][index]) for index in selected]
    pins = dict(original_plan['input_sha256'])
    worker = Path(__file__).with_name('run_compact_numerical_holdout_case.py')
    assessor = Path(__file__).with_name('assess_compact_numerical_holdout.py')
    for path in (Path(__file__).resolve(), worker, assessor, source / 'plan.json',
                 source / 'run_001/assessment.json', shared_owner,
                 Path(__file__).with_name('characterize_compact_propagation.py')):
        pins[str(path)] = digest(path)
    for path, sha in pins.items():
        assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
        assert digest(Path(path)) == sha, path
    header = (source / 'batch.cir').read_text().split('VIN_0 ', 1)[0]
    settings = [('subset_baseline', 2, '1e-5', '1e-10', 34, 2),
                ('timestep_only', 1, '1e-5', '1e-10', 34, 2),
                ('relative_tolerance_only', 2, '1e-6', '1e-10', 34, 2),
                ('absolute_tolerance_only', 2, '1e-5', '1e-11', 34, 2),
                ('duration_only', 2, '1e-5', '1e-10', 50, 3)]
    prepared = []
    for label, step, rel, absolute, stop, repetitions in settings:
        folder = out / label
        folder.mkdir()
        lines = header.replace('.options timeint reltol=1e-5 abstol=1e-10',
            f'.options timeint reltol={rel} abstol={absolute}').rstrip().splitlines()
        lines[0] = '* Four selected independent numerical/settling holdout fixtures.'
        columns = []
        for index, case in enumerate(cases):
            aliases = {**SUPPLIES, case['input']: f'IN_{index}', case['output']: f'OUT_{index}',
                       **{pin: 'VDD' if value else '0' for pin, value in case['side_inputs'].items()}}
            ramp = case['full_ramp_ps']
            lines.extend([f'VIN_{index} IN_{index} 0 PULSE(0 1.8 2n {ramp:.12g}p {ramp:.12g}p 5n 16n)',
                f'XDUT_{index} '+' '.join(aliases[pin] for pin in case['ports'])+' '+case['master']])
            if case['external_load_pf'] > 0:
                lines.append(f'CLOAD_{index} OUT_{index} 0 {case["external_load_pf"]:.12g}p')
            columns.extend([f'V(IN_{index})', f'V(OUT_{index})'])
        lines.extend([f'.tran 2p {stop}n 0 {step}p', '.print tran '+' '.join(columns), '.end'])
        deck = folder / 'batch.cir'
        deck.write_text('\n'.join(lines)+'\n')
        plan = dict(input_sha256={**pins, str(deck): digest(deck)}, fixtures=cases,
            original_case_indices=selected, pvt=original_plan['pvt'], stop_ns=stop,
            expected_repetitions=repetitions, maximum_step_ps=step, reltol=float(rel),
            abstol=float(absolute), independent_control=label,
            subset_baseline_required_before_attributing_numerical_differences=True,
            physical_timing_qualified=False, release_qualified=False)
        path = folder / 'plan.json'
        save(path, plan)
        prepared.append(dict(label=label, plan=str(path), plan_sha256=digest(path)))
    save(out / 'plan.json', dict(input_sha256=pins, cases=prepared,
        original_case_indices=selected, shared_deadline_uptime=deadline,
        scope='Selected SF-40 fixtures only; subset/global solver-context effects are '
              'measured with a new subset baseline. Controls change one setting at a time. '
              'Duration control retains the pulse train and measures a third opportunity. '
              'No numerical uncertainty bound or timing library is qualified.',
        physical_timing_qualified=False, release_qualified=False, adopted=False))
    results = []
    for case in prepared:
        if time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:
            results.append(dict(case, state='deadline_before_case'))
            continue
        folder = Path(case['plan']).parent
        with (folder / 'worker.log').open('x') as log:
            child = subprocess.Popen([sys.executable, str(worker), '--plan', case['plan'],
                '--campaign', str(out)], cwd=root, stdout=log, stderr=subprocess.STDOUT,
                start_new_session=True,
                env=dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1'))
            save(folder / 'worker_owner.json', dict(worker_pid=child.pid, deadline_uptime=deadline))
            save(out / 'status.json', dict(state='running_or_queued_selected_holdout',
                label=case['label'], worker_pid=child.pid, deadline_uptime=deadline, release_qualified=False))
            code = child.wait()
        receipt = folder / 'run_001/assessment.json'
        state = folder / 'run_001/status.json'
        results.append(dict(case, worker_exit=code,
            state=json.loads(state.read_text())['state'] if state.exists() else 'missing_worker_state',
            assessment=str(receipt) if receipt.exists() else None,
            assessment_sha256=digest(receipt) if receipt.exists() else None))
        save(out / 'case_results.json', results)
    save(out / 'assessment.json', dict(cases=results,
        all_selected_controls_have_terminal_receipts=all(c.get('assessment') for c in results),
        physical_timing_qualified=False, numerical_domain_enclosure_qualified=False,
        release_qualified=False, adopted=False))
    save(out / 'status.json', dict(state='terminal_selected_holdout_campaign',
        deadline_uptime=deadline, release_qualified=False))


if __name__ == '__main__':
    main()
