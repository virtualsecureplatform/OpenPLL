"""Collect completed reset pulse grids and report finite observations, never a bound."""
import argparse
import json
import os
from pathlib import Path
import time

from common_v3 import ROOT, save, sha, verify
from resources import identity


def validate_rows(plan, rows):
    expected = {(corner, c['master'], c['width_ps'], c['full_ramp_ps']): c
                for corner in plan['corners'] for c in plan['cases']}
    if len(expected) != len(plan['corners']) * len(plan['cases']):
        raise ValueError('unique planned cases required')
    seen = set()
    for row in rows:
        key = tuple(row[k] for k in ('corner','master','width_ps','full_ramp_ps'))
        if key not in expected or key in seen:
            raise ValueError('unexpected or duplicate observation')
        seen.add(key)
        if any(row[k] != value for k,value in expected[key].items()):
            raise ValueError('observation differs from prospective plan')
        checks = [row[k] for k in ('opposite_prestate_verified','final_state_verified',
                  'reset_released_verified','stimulus_verified')]
        if any(type(v) is not bool for v in checks + [row['fixture_passed']]):
            raise ValueError('explicit boolean observation required')
        if row['fixture_passed'] != all(checks):
            raise ValueError('inconsistent fixture result')
    if seen != expected.keys():
        raise ValueError('complete planned observations required')


def summary(rows):
    selected = [r for r in rows if r['width_ps'] == 2000]
    expected = {(c, 'sky130_fd_sc_hs__' + m, ramp)
                for c in ('tt','ff','ss','sf','fs')
                for m in ('dfrtp_1','dfrtp_2','dfrtp_4','dfstp_1','dfstp_2')
                for ramp in (20,400,1600)}
    actual = {(r['corner'],r['master'],r['full_ramp_ps']) for r in selected}
    if len(selected) != len(expected) or actual != expected:
        raise ValueError('all 75 independently observed 2 ns fixtures required')
    controls = [r for r in rows if r['negative_control']]
    return dict(observations=len(rows), failed_cases=[r for r in rows if not r['fixture_passed']],
                no_pulse_controls=len(controls), all_no_pulse_controls_pass=all(r['fixture_passed'] for r in controls),
                declared_2ns_pulse_observations=len(selected),
                all_declared_2ns_pulse_observations_pass=all(r['fixture_passed'] for r in selected))


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    os.sched_setaffinity(0, {19})
    save(output / 'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid())) )
    base = ROOT / 'build/signoff400'
    sources = [base / n for n in ('selected_keeper_reset_pulse_grid_1506',
                                  'selected_keeper_reset_pulse_slow_grid_1507')]
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME) + 86400
    try:
        for source in sources:
            while True:
                state = json.loads((source / 'status.json').read_text())
                if state['state'] == 'native_reset_pulse_grid_complete':
                    break
                if state['state'] == 'stopped_without_qualification':
                    raise RuntimeError('pulse campaign stopped: ' + str(source))
                owner = json.loads((source / 'owner.json').read_text())
                if identity(owner['pid']) != owner['birth']:
                    raise RuntimeError('pulse campaign owner absent without completion')
                if time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:
                    raise TimeoutError('completed pulse campaign observation deadline')
                save(output / 'status.json', dict(state='waiting_for_completed_reset_pulse_grids', source=str(source), release_ready=False))
                time.sleep(10)
        envelope = base / 'selected_keeper_reset_fixture_envelope_1505/assessment.json'
        a = json.loads(envelope.read_text())
        verify(a['input_sha256'])
        verify(a['artifacts'])
        pins = {str(p):sha(p) for p in [envelope,Path(__file__).resolve()]}
        all_rows, model_hashes, source_hashes = [], set(), set()
        for source in sources:
            receipt, plan_path, detail = [source / n for n in ('assessment.json','plan.json','observations.json')]
            r = json.loads(receipt.read_text())
            verify(r['input_sha256'])
            verify(r['artifacts'])
            if r['artifacts'].get(str(detail)) != sha(detail):
                raise ValueError('pinned observations required')
            plan, rows = json.loads(plan_path.read_text()), json.loads(detail.read_text())
            validate_rows(plan, rows)
            if r['cases'] != len(rows) or r['failed_cases'] != sum(not row['fixture_passed'] for row in rows):
                raise ValueError('receipt and observations disagree')
            model = source / 'cells.spice'
            if r['input_sha256'].get(str(model)) != sha(model):
                raise ValueError('pinned extracted models required')
            model_hashes.add(sha(model))
            original = base / 'prototype_v3_fixed_divider_digital_capacitance_001/IntegerPLL_ProgrammedCore/capacitance.spice'
            source_hashes.add(r['input_sha256'].get(str(original)))
            pins.update({str(p):sha(p) for p in [receipt,plan_path,detail]})
            all_rows += rows
        if len(model_hashes) != 1 or len(source_hashes) != 1 or None in source_hashes:
            raise ValueError('same extracted cell sources required across campaigns')
        result = summary(all_rows)
        detail = output / 'observations.json'
        save(detail, all_rows)
        verify(pins)
        save(output / 'assessment.json', dict(input_sha256=pins, artifacts={str(detail):sha(detail)},
             **result, routed_slew_comparison=a['corners'],
             discrete_grid_is_not_continuous_bound=True, minimum_pulse_bound_qualified=False,
             actual_reset_slew_and_load_envelope_qualified=False,
             recovery_removal_qualified=False, routed_reset_timing_qualified=False,
             external_reset_contract_qualified=False, release_ready=False))
        save(output / 'status.json', dict(state='completed_reset_pulse_campaigns_reviewed', release_ready=False))
    except BaseException as error:
        save(output / 'status.json', dict(state='stopped_without_qualification', reason=repr(error), release_ready=False))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    run(parser.parse_args().output.resolve())
