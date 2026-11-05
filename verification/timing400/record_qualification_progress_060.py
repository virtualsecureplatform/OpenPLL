#!/usr/bin/env python3
"""Record compiled local operators, integral controls, and actual assembly state."""
from datetime import datetime, timezone
import json
from pathlib import Path
import time

from compile_local_C_operators_v2 import digest, save
from record_qualification_progress_045 import process


def main():
    root = Path(__file__).resolve().parents[2]
    base = root/'build/timing400/release_001'
    owner = base/'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    op_path = base/'local_C_operator_compilation_001/assessment.json'
    control_path = base/'local_C_field_integral_controls_001/assessment.json'
    operators, controls = [json.loads(p.read_text()) for p in [op_path, control_path]]
    assert operators['all12_native_small_case_corner_operator_controls_passed']
    assert operators['nominal_operators_match_owned_native_kernels_and_complete_domain_keys']
    assert controls['local_field_integral_controls_passed']
    jobs = []
    for p in Path('/proc').glob('[0-9]*'):
        try:
            argv = (p/'cmdline').read_bytes().split(b'\0')
            if not any(a.endswith((b'/compile_local_C_operators_v2.py', b'/assemble_local_C_matrix.py')) for a in argv):
                continue
            row = process(int(p.name))
            if row['live']:
                jobs.append(row)
        except (ProcessLookupError, FileNotFoundError):
            continue
    stages = {}
    for name in ['DCO_local_C_operators_min_001', 'DCO_local_C_operators_max_001', 'DCO_local_C_matrix_nom_001']:
        path = base/name/'status.json'
        if path.exists():
            stages[name] = json.loads(path.read_text())
    prior = base/'qualification_progress_059.json'
    progress = json.loads(prior.read_text())
    inputs = [Path(__file__).resolve(), prior, owner, op_path, control_path]
    frozen = {'verification/release_requirements_400mhz.json': '02911569a2538d8b4d6c3139decdf7ec4d7c33bf2cbad85eed442947c0022b52',
        'verification/release_plan_400mhz.json': '2d6d5ed4404df842d64d42d68ebe593e4f627e65b4f90aaa48bef5f991e94b02'}
    for name, expected in frozen.items():
        assert digest(root/name) == expected
        inputs.append(root/name)
    evidence = dict(operator_compilation_receipt=str(op_path.relative_to(root)),
        field_integral_control_receipt=str(control_path.relative_to(root)),
        nominal_DCO_events=operators['nominal_DCO_events'], nominal_local_operators=operators['nominal_local_operators'],
        native_small_case_corner_controls=12, voltage_fields=operators['voltage_fields'],
        signed_shielding_and_arithmetic_residuals_preserved=True,
        exact_area_and_line_and_independent_fringe_integrals_passed=True,
        stages_at_observation=stages, live_CPU_jobs=jobs,
        original_deadline_uptime=deadline, budget_reset=False,
        runtime_model_eligible=False, release_qualified=False, adopted=False)
    progress.update(observed_utc=datetime.now(timezone.utc).isoformat(),
        classification='owned_local_C_operators_compiled_independent_field_integral_controls_passed_matrix_assembly_in_progress',
        evidence_sha256={str(p.relative_to(root)): digest(p) for p in inputs},
        local_C_operator_assembly=evidence, active_distributed_RC_followups=jobs,
        native_analog_jobs=[], native_analog_count=0, release_qualified=False, adopted=False,
        physical_whole_pll_passes=0)
    progress['next_actions'] = [
        'Complete full signed private-node C matrix assembly, verify zero-wire-R collapse and diagnose global passivity',
        'Complete min/max RC operators and qualify R values, spatial/numerical error, external feeds and runtime adaptor',
        'Run qualified golden-Xyce four-mode frequency/calibration and frozen nominal1.8V/15PVT timing and wholePLL release gates']
    snapshot = base/'qualification_progress_060.json'
    assert not snapshot.exists()
    save(snapshot, progress)
    overview = root/'build/timing450/implementation_assessment.json'
    state = json.loads(overview.read_text())
    state['latest_400mhz_qualification_progress'] = str(snapshot.relative_to(root))
    state['active_400mhz_local_C_operator_assembly'] = evidence
    state['active_400mhz_distributed_RC_followups'] = jobs
    state['active_400mhz_distributed_RC_check'] = dict(owner=str(owner.relative_to(root)),
        state='local_operators_compiled_matrix_assembly_and_runtime_qualification_open',
        deadline_uptime=deadline, native_analog_jobs=0, native_CAD_jobs=0, release_qualified=False)
    for key in ['release_qualified', 'selected', 'timing_closure_complete']:
        state[key] = False
    save(overview, state)
    print(json.dumps(evidence, indent=2))


if __name__ == '__main__':
    main()
