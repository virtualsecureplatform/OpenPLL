#!/usr/bin/env python3
"""Retain terminal timeout evidence without restarting the original campaign."""
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import time
from compile_local_C_operators_v2 import digest, save
from record_qualification_progress_045 import process


def main():
    root = Path(__file__).resolve().parents[2]
    base = root / 'build/timing400/release_001'
    owner = base / 'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline
    requirements = root / 'verification/release_requirements_400mhz.json'
    plan = root / 'verification/release_plan_400mhz.json'
    assert digest(requirements) == '02911569a2538d8b4d6c3139decdf7ec4d7c33bf2cbad85eed442947c0022b52'
    assert digest(plan) == '2d6d5ed4404df842d64d42d68ebe593e4f627e65b4f90aaa48bef5f991e94b02'
    inputs = [Path(__file__), owner, requirements, plan]
    cases = {}
    for name, target in [('DCO_domain_nom_tt27_c0_f247_80ns_stock_threaded_002', 80e-9),
                         ('DCO_native_zero_wire_R_nom_tt27_c0_f247_25ns_numeric_002', 25e-9)]:
        folder = base / name
        state = json.loads((folder / 'status.json').read_text())
        assert 'timeout' in state['state'] and state['deadline_uptime'] == deadline
        assert not process(state['runner_pid'])['live']
        # Owners do not all retain the native PID after timeout. The last
        # progress snapshot retains the exact process identity for both cases.
        previous = json.loads((base / 'qualification_progress_084.json').read_text())
        prior_native = previous['throughput_followup']['active_native_transients'][name]['native']
        assert not process(prior_native['pid'])['live']
        text = (folder / 'point.cir.prn').read_text()
        lines = text.splitlines()
        trailing_fragment = bool(text and not text.endswith('\n'))
        if trailing_fragment: lines.pop()
        assert lines[0].split() == ['Index', 'TIME', 'V(PLLOUT)', 'I(VVPWR)']
        assert 'End of Xyce(TM) Simulation' not in lines
        rows = []
        for line in lines[1:]:
            if not line.strip(): continue
            fields = line.split(); assert len(fields) == 4 and int(fields[0]) == len(rows)
            row = tuple(map(float, fields[1:])); assert all(math.isfinite(value) for value in row)
            assert not rows or rows[-1][0] < row[0]
            rows.append(row)
        assert rows and rows[0][0] == 0 and rows[-1][0] < target
        cases[name] = dict(status=state, source_native_identity=prior_native,
            native_and_owner_confirmed_stopped=True, accepted_samples=len(rows),
            last_accepted_time_s=rows[-1][0], required_duration_s=target,
            trailing_unterminated_fragment_excluded_from_metrics=trailing_fragment,
            full_native_completion_verified=False, timeout_is_inconclusive=True)
        inputs.extend([folder / 'status.json', folder / 'owner.json', folder / 'input_manifest.json',
                       folder / 'point.cir.prn', folder / 'native.log'])
    startup = base / 'DCO_ideal_wire_startup_prefix_checks_001/assessment.json'
    assert json.loads(startup.read_text())['startup_comparison_independently_verified']
    inputs.append(startup)
    previous_path = base / 'qualification_progress_084.json'; inputs.append(previous_path)
    result = json.loads(previous_path.read_text())
    work = result['throughput_followup']; work['active_native_transients'] = {}
    work['original_campaign_terminal_result'] = dict(state='timeout_inconclusive',
        deadline_uptime=deadline, budget_restarted=False, cases=cases,
        automatic_identical_retry_scheduled=False, physical_whole_pll_passes=0,
        release_qualified=False, adopted=False)
    for name, entry in work['threaded_solver_followup']['pipeline'].items():
        state = json.loads((base / name / 'status.json').read_text())
        entry.update(status=state, runner=process(state['runner_pid']))
        assert not entry['runner']['live'], name
        if 'native_pid' in state: entry['native'] = process(state['native_pid'])
    nested = result['restored_self_C_operator_followup']
    nested.update(current_native_engines=[], native_points=cases, active_check_statuses=cases,
                  throughput_followup=work)
    out = base / 'campaign_deadline_001'; out.mkdir(exist_ok=False)
    audit = dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        original_campaign_deadline_uptime=deadline, original_budget_seconds=43200,
        campaign_result='timeout_inconclusive', original_runs_stopped=True,
        budget_restarted=False, automatic_identical_retry_scheduled=False, cases=cases,
        startup_diagnostic_retained=True, qualified_whole_pll_passes=0,
        open_release_gates=[gate['id'] for gate in json.loads(plan.read_text())['gates']],
        release_qualified=False, adopted=False,
        evidence_sha256={str(path.resolve()): digest(path) for path in inputs})
    save(out / 'assessment.json', audit)
    result.update(observed_utc=audit['observed_utc'], classification='original_12h_campaign_timeout_inconclusive',
        throughput_followup=work, restored_self_C_operator_followup=nested,
        native_analog_jobs=[], native_analog_count=0, current_native_CAD_and_analog_engines=[],
        release_qualified=False, adopted=False, physical_whole_pll_passes=0,
        evidence_sha256={str((out / 'assessment.json').resolve()): digest(out / 'assessment.json')})
    snapshot = base / 'qualification_progress_085.json'; assert not snapshot.exists(); save(snapshot, result)
    overview = root / 'build/timing450/implementation_assessment.json'
    state = json.loads(overview.read_text())
    state.update(latest_400mhz_qualification_progress=str(snapshot.relative_to(root)),
        active_400mhz_restored_self_C_operator_followup=nested,
        active_400mhz_throughput_followup=work, release_qualified=False,
        selected=False, timing_closure_complete=False)
    save(overview, state)
    print('Progress085: original campaign ended inconclusive; partial evidence retained; no release.')


if __name__ == '__main__':
    main()
