#!/usr/bin/env python3
"""Record validated missing-self-pair tracing and the live corrected compiler."""
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
    trace_path = base/'DCO_C_owner_trace_001/assessment.json'
    controls_path = base/'DCO_self_C_extension_controls_002/assessment.json'
    trace, controls = [json.loads(p.read_text()) for p in [trace_path, controls_path]]
    assert trace['nominal_native_C_devices_and_feedback_unchanged']
    assert controls['all12_contact_normalized_self_operator_controls_passed']
    assert controls['all_original_native_energy_operators_exactly_preserved']
    assert controls['original_operators'] == 83838 and controls['added_self_operators'] == 10050
    jobs, engines = [], []
    for p in Path('/proc').glob('[0-9]*'):
        try:
            args = [s.decode() for s in (p/'cmdline').read_bytes().split(b'\0') if s]
            if any(s.endswith('/compile_local_C_operators_v5.py') for s in args):
                row = process(int(p.name))
                if row['live']:
                    jobs.append(row)
            name = (p/'comm').read_text().strip()
            if name in ['Xyce', 'ngspice', 'magicdnull']:
                row = process(int(p.name))
                if row['live']:
                    engines.append(dict(kind=name, **row))
        except (FileNotFoundError, ProcessLookupError):
            continue
    assert not engines
    output = base/'DCO_local_C_operators_nom_self_002'
    status = json.loads((output/'status.json').read_text()) if (output/'status.json').exists() else dict(state='reading_retained_native_plane_residues')
    assert jobs or (output/'assessment.json').exists()
    previous = base/'qualification_progress_061.json'
    progress = json.loads(previous.read_text())
    evidence = dict(owner_trace_receipt=str(trace_path.relative_to(root)),
        normalized_self_operator_controls=str(controls_path.relative_to(root)),
        all12_native_owner_equivalence_controls_passed=True,
        actual_DCO_native_C_devices_and_feedback_preserved=True,
        all12_self_operator_controls_and_exact_native_operator_identity_passed=True,
        unchanged_small_case_native_operators=83838, added_small_case_self_operators=10050,
        actual_contact_normalizations_checked=78,
        contact_decoder_uses_exact_retained_native_surface_residue_observations=True,
        no_native_extraction_repeated_for_contact_decoder_fix=True,
        current_compiler='verification/timing400/compile_local_C_operators_v5.py',
        current_operator_output=str(output.relative_to(root)), current_status_at_observation=status,
        live_CPU_jobs=jobs, native_CAD_and_analog_engines=engines,
        original_nominal_C_matrix_still_rejected=True, corrected_matrix_passivity_proven=False,
        prepared_incremental_assembler='verification/timing400/assemble_DCO_self_C_increment.py',
        incremental_reuse_requires_exact_full_native_operator_identity=True,
        original_deadline_uptime=deadline, budget_restarted=False,
        runtime_model_eligible=False, release_qualified=False, adopted=False)
    inputs = [Path(__file__).resolve(), owner, previous, trace_path, controls_path,
        base/'magic_C_owner_controls_001/assessment.json', base/'DCO_self_C_extension_controls_001/assessment.json',
        base/'DCO_local_C_operators_nom_self_001/failure_and_supersession.json',
        Path(__file__).with_name('compile_local_C_operators_v5.py'),
        Path(__file__).with_name('separate_DCO_self_C_increment.py'),
        Path(__file__).with_name('assemble_DCO_self_C_increment.py')]
    for name, expected in {
        'verification/release_requirements_400mhz.json': '02911569a2538d8b4d6c3139decdf7ec4d7c33bf2cbad85eed442947c0022b52',
        'verification/release_plan_400mhz.json': '2d6d5ed4404df842d64d42d68ebe593e4f627e65b4f90aaa48bef5f991e94b02'}.items():
        assert digest(root/name) == expected
        inputs.append(root/name)
    progress.update(observed_utc=datetime.now(timezone.utc).isoformat(),
        classification='native_owner_trace_and12_normalized_self_operator_controls_passed_full_corrected_operator_compilation_in_progress',
        evidence_sha256={str(p.relative_to(root)): digest(p) for p in inputs},
        restored_self_C_operator_followup=evidence, active_distributed_RC_followups=jobs,
        native_analog_jobs=[], native_analog_count=0, current_native_CAD_and_analog_engines=[],
        release_qualified=False, adopted=False, physical_whole_pll_passes=0)
    progress['next_actions'] = [
        'Finish compile_local_C_operators_v5 full nominal output; do not restart a live compiler or any completed native extraction',
        'Prove every original energy operator identical using separate_DCO_self_C_increment, then assemble only the missing terms onto the retained numerical sum',
        'Require fresh zero-R conservation and full signed passivity of the corrected matrix before diagnostic SPICE export or transient',
        'Complete corrected min/max, numerical/integration qualification and all frozen nominal1.8V/15PVT four-mode release gates']
    snapshot = base/'qualification_progress_062.json'
    assert not snapshot.exists()
    save(snapshot, progress)
    overview = root/'build/timing450/implementation_assessment.json'
    state = json.loads(overview.read_text())
    state['latest_400mhz_qualification_progress'] = str(snapshot.relative_to(root))
    state['active_400mhz_restored_self_C_operator_followup'] = evidence
    state['active_400mhz_distributed_RC_followups'] = jobs
    state['active_400mhz_distributed_RC_check'] = dict(owner=str(owner.relative_to(root)),
        state='contact_normalized_missing_self_C_compilation_running_original_matrix_rejected',
        deadline_uptime=deadline, native_analog_jobs=0, native_CAD_jobs=0, release_qualified=False)
    for key in ['release_qualified', 'selected', 'timing_closure_complete']:
        state[key] = False
    save(overview, state)
    print('Progress062: nominal owner trace and all twelve normalized self-pair controls passed; full corrected compilation live.')


if __name__ == '__main__':
    main()
