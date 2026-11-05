#!/usr/bin/env python3
"""Record corner support identity and live max-energy/DC qualification work."""
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from compile_local_C_operators_v2 import digest,save
from record_qualification_progress_045 import process


def main():
    root=Path(__file__).resolve().parents[2]
    base=root/'build/timing400/release_001'
    owner=base/'distributed_RC_model_qualification_001/owner.json'
    deadline=json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME)<deadline
    proof=base/'DCO_self_C_support_corner_identity_001/assessment.json'
    identity=json.loads(proof.read_text())
    assert identity['all_added_self_support_geometries_identical_across_RC_corners']
    inputs=[Path(__file__).resolve(),owner,proof,base/'qualification_progress_063.json',
        Path(__file__).with_name('assess_DCO_domain_point_STD.py'),
        Path(__file__).with_name('trace_DCO_max_C_mode_energy.py')]
    for name,expected in {
        'verification/release_requirements_400mhz.json':'02911569a2538d8b4d6c3139decdf7ec4d7c33bf2cbad85eed442947c0022b52',
        'verification/release_plan_400mhz.json':'2d6d5ed4404df842d64d42d68ebe593e4f627e65b4f90aaa48bef5f991e94b02'}.items():
        assert digest(root/name)==expected
        inputs.append(root/name)
    jobs,engines=[],[]
    for p in Path('/proc').glob('[0-9]*'):
        try:
            args=[s.decode() for s in (p/'cmdline').read_bytes().split(b'\0') if s]
            if any(s.endswith('/trace_DCO_max_C_mode_energy.py') for s in args):
                row=process(int(p.name))
                if row['live']:jobs.append(row)
            if (p/'comm').read_text().strip() in ['Xyce','ngspice','magicdnull']:
                row=process(int(p.name))
                if row['live']:engines.append(row)
        except (FileNotFoundError,ProcessLookupError):
            continue
    assert len(engines)<=4
    statuses={}
    for folder in ['DCO_max_C_mode_energy_trace_001','DCO_domain_nom_tt27_c0_f247_80ns_klu_001',
                   'DCO_domain_nom_tt27_c0_f247_C_free_DC_001']:
        path=base/folder/'status.json'
        statuses[folder]=json.loads(path.read_text())
        assessment=base/folder/'assessment.json'
        if assessment.exists():inputs.append(assessment)
    progress=json.loads((base/'qualification_progress_063.json').read_text())
    followup=progress['restored_self_C_operator_followup']
    followup.update(all_added_self_support_geometries_identical_across_RC_corners=True,
        all_added_self_supports_have_GDS_coverage_at_all_three_corners=True,
        support_geometry_identity_receipt=str(proof.relative_to(root)),
        active_check_statuses=statuses,current_native_engines=engines,
        native_points={k:v for k,v in statuses.items() if k.startswith('DCO_domain_')},
        prepared_completed_STD_native_point_reader='verification/timing400/assess_DCO_domain_point_STD.py',
        no_completed_native_case_repeated_for_output_reader_fix=True)
    progress.update(observed_utc=datetime.now(timezone.utc).isoformat(),
        classification='all_corner_added_support_geometry_coverage_proven_max_C_energy_trace_and_nominal_native_checks_live',
        restored_self_C_operator_followup=followup,active_distributed_RC_followups=jobs,
        native_analog_jobs=engines,native_analog_count=len(engines),current_native_CAD_and_analog_engines=engines,
        evidence_sha256={str(p.relative_to(root)):digest(p) for p in inputs})
    snapshot=base/'qualification_progress_064.json'
    assert not snapshot.exists()
    save(snapshot,progress)
    overview=root/'build/timing450/implementation_assessment.json'
    state=json.loads(overview.read_text())
    state.update(latest_400mhz_qualification_progress=str(snapshot.relative_to(root)),
        active_400mhz_restored_self_C_operator_followup=followup,active_400mhz_distributed_RC_followups=jobs,
        release_qualified=False,selected=False,timing_closure_complete=False)
    state['active_400mhz_distributed_RC_check'].update(native_analog_jobs=len(engines),
        state='all_corner_added_support_geometry_proven_max_energy_trace_and_nominal_native_checks')
    save(overview,state)
    print('Progress064: added self-C support geometry shared across min/nom/max; electrical maximum-C remains rejected.')


if __name__=='__main__':
    main()
