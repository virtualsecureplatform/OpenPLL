"""Reassess closed pulse grids using a window strictly before each planned ramp."""
import argparse
import json
import os
from pathlib import Path
import time
import numpy as np
from common_v3 import ROOT, save, sha, verify
from resources import identity
from run_keeper_reset_pulse_grid_v3 import assess, stable
from review_keeper_reset_pulse_campaigns import validate_rows, summary


def reassess(t, q, control, case):
    result = assess(t, q, control, case['reset_state'], case['negative_control'])
    # Every tested pulse is centered at 10 ns. Observe 200--100 ps before
    # the start of its input ramp, including the hypothetical no-pulse ramp.
    leading = 10e-9 - case['full_ramp_ps'] * 1e-12 / 2
    start, end = leading - 200e-12, leading - 100e-12
    mask = (t >= start) & (t <= end)
    if np.count_nonzero(mask) < 10 or not end < leading:
        raise ValueError('adequately sampled strictly pre-stimulus window required')
    if not stable(control[mask], 1):
        raise ValueError('control must be inactive throughout pre-stimulus observation')
    original = result['opposite_prestate_verified']
    result['opposite_prestate_verified'] = stable(q[mask], 1-case['reset_state'])
    result['fixture_passed'] = all(result[k] for k in ('opposite_prestate_verified',
        'final_state_verified','reset_released_verified','stimulus_verified'))
    result.update(original_prestate_verified=original,
        prestimulus_window_ns=[start*1e9,end*1e9], ramp_leading_ns=leading*1e9,
        prestimulus_Q_min_V=float(np.min(q[mask])), prestimulus_Q_max_V=float(np.max(q[mask])))
    return result


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    os.sched_setaffinity(0, {19})
    save(output / 'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid())) )
    base = ROOT / 'build/signoff400'
    review = base / 'selected_keeper_reset_pulse_campaign_review_1509'
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME)+86400
    try:
        while True:
            state = json.loads((review / 'status.json').read_text())['state']
            if state == 'completed_reset_pulse_campaigns_reviewed':
                break
            if state == 'stopped_without_qualification':
                raise RuntimeError('original review stopped')
            owner = json.loads((review / 'owner.json').read_text())
            if identity(owner['pid']) != owner['birth']:
                raise RuntimeError('review owner absent without completion')
            if time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:
                raise TimeoutError('original review observation deadline')
            save(output / 'status.json', dict(state='waiting_for_completed_original_review', release_ready=False))
            time.sleep(10)
        receipt = review / 'assessment.json'
        a = json.loads(receipt.read_text())
        verify(a['input_sha256'])
        verify(a['artifacts'])
        helpers = ['run_keeper_reset_pulse_grid_v3.py','review_keeper_reset_pulse_campaigns.py']
        pins = {str(p):sha(p) for p in [receipt,Path(__file__).resolve(),
                *[Path(__file__).with_name(n) for n in helpers]]}
        rows = []
        for name in ('selected_keeper_reset_pulse_grid_1506','selected_keeper_reset_pulse_slow_grid_1507'):
            source = base / name
            r = json.loads((source / 'assessment.json').read_text())
            verify(r['input_sha256'])
            verify(r['artifacts'])
            plan = json.loads((source / 'plan.json').read_text())
            source_rows = []
            for corner in plan['corners']:
                directory = base / 'selected_keeper_reset_pulse_grid_1504/tt' if corner == 'tt' and name.endswith('1506') else source / corner
                waveform = directory / 'waveform.dat'
                pins[str(waveform)] = sha(waveform)
                x = np.loadtxt(waveform, skiprows=1)
                for i,case in enumerate(plan['cases']):
                    source_rows.append(dict(corner=corner, **{**case,
                        **reassess(x[:,0],x[:,i+1],x[:,len(plan['cases'])+i+1],case)}))
            validate_rows(plan,source_rows)
            rows += source_rows
            pins.update({str(p):sha(p) for p in [source / 'assessment.json',source / 'plan.json']})
        detail = output / 'observations.json'
        save(detail,rows)
        result = summary(rows)
        verify(pins)
        save(output / 'assessment.json', dict(input_sha256=pins, artifacts={str(detail):sha(detail)},
             **result, original_observations_preserved=True, native_rerun=False,
             window_rule='200 to 100 ps before each planned ramp leading edge',
             minimum_pulse_bound_qualified=False, routed_reset_timing_qualified=False, release_ready=False))
        save(output / 'status.json', dict(state='closed_pulse_grids_reassessed_before_stimulus', release_ready=False))
    except BaseException as error:
        save(output / 'status.json', dict(state='stopped_without_qualification',reason=repr(error),release_ready=False))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    run(parser.parse_args().output.resolve())
