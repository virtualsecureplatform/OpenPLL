#!/usr/bin/env python3
"""Record validated native RC substrate context and bounded assembled-layout work."""
from datetime import datetime,timezone
from pathlib import Path
import time
from record_qualification_progress_031 import ROOT,BASE,read,digest,write
from check_compact_clock_tree import verify


def process(pid):
    p=Path('/proc')/str(pid)
    try:
        state=(p/'stat').read_text().rsplit(')',1)[1].split()[0]
        args=[s.decode() for s in (p/'cmdline').read_bytes().split(b'\0') if s]
        return dict(pid=pid,live=state!='Z' and bool(args),argv=args)
    except (FileNotFoundError,ProcessLookupError):return dict(pid=pid,live=False)


def main():
    names=['qualification_progress_044.json','magic_RC_substrate_C_patch_001/assessment.json',
        'magic_RC_substrate_C_build_001/assessment.json','magic_RC_substrate_C_default_controls_001/assessment.json',
        'magic_RC_substrate_C_context_controls_001/assessment.json','DCO_RC_substrate_C_equivalence_001/assessment.json']
    paths=[BASE/n for n in names]+[Path(__file__).resolve(),ROOT/'verification/timing400/run_full_layout_RC_substrate_capacitance.py',
        ROOT/'verification/timing400/collect_full_layout_RC_substrate_capacitance.py',
        ROOT/'verification/release_requirements_400mhz.json',ROOT/'verification/release_plan_400mhz.json']
    assert digest(paths[-2])=='02911569a2538d8b4d6c3139decdf7ec4d7c33bf2cbad85eed442947c0022b52'
    assert digest(paths[-1])=='2d6d5ed4404df842d64d42d68ebe593e4f627e65b4f90aaa48bef5f991e94b02'
    default=verify(BASE/'magic_RC_substrate_C_default_controls_001/assessment.json')
    small=verify(BASE/'magic_RC_substrate_C_context_controls_001/assessment.json')
    dco=verify(BASE/'DCO_RC_substrate_C_equivalence_001/assessment.json')
    assert default['installed_and_isolated_C_devices_feedback_equal'] and default['native_CAD_runs']==24
    assert small['installed_RC_and_opt_in_C_only_C_and_devices_equal'] and small['native_CAD_runs']==24
    assert dco['full_DCO_trace_accounting_passed'] and dco['installed_RC_and_opt_in_C_only_exact_C_and_devices_identical']
    assert all(r['installed_RC_context_and_C_only_context_exact_C_devices_identical'] and r['full_wire_R_extraction_skipped'] for r in dco['results'])
    jobs=[]
    for corner in ['min','nom','max']:
        source=BASE/'poly_metal_full_RC_substrate_capacitance_001'/corner
        collector=BASE/'RC_substrate_capacitance_collection_001'/corner
        owner=read(source/'owner.json');state=read(source/'status.json');assessment_owner=read(collector/'owner.json')
        assert owner['deadline_uptime']==assessment_owner['deadline_uptime']==3136114.566309955
        paths.extend([source/'owner.json',source/'input_manifest.json',collector/'owner.json'])
        jobs.append(dict(corner=corner,source=str(source.relative_to(ROOT)),collector=str(collector.relative_to(ROOT)),
            state=state,runner=process(owner['runner_pid']),native=process(state.get('native_pid',-1)),
            assessor=process(assessment_owner['runner_pid']),deadline_uptime=owner['deadline_uptime'],
            remaining_budget_s=max(0,owner['deadline_uptime']-time.clock_gettime(time.CLOCK_BOOTTIME))))
    analog=[]
    for p in Path('/proc').glob('[0-9]*'):
        try:
            if (p/'comm').read_text().strip() in ['Xyce','ngspice']:
                r=process(int(p.name))
                if r['live']:analog.append(r)
        except (FileNotFoundError,ProcessLookupError):continue
    assert len(analog)<=4
    prior=read(BASE/'qualification_progress_044.json')
    progress={k:v for k,v in prior.items() if k not in ['observed_utc','classification','evidence_sha256','next_actions','native_analog_jobs','native_analog_count']}
    context=dict(prior['RC_substrate_context_work'])
    context.update(new_opt_in_mode_native_controls_passed=True,opt_in_default_native_CAD_runs=24,
        opt_in_small_RC_context_native_CAD_runs=24,opt_in_actual_DCO_native_CAD_runs=3,
        all3_DCO_corner_C_and_devices_exactly_match_installed_RC_context=True,
        automatic_full_wire_R_extraction_verified_skipped=True,all3_DCO_native_feedback_equal=True,
        DCO_corner_accounting_results=dco['results'],assembled_layout_raw_C_jobs=jobs,
        full_parent_trace_enabled=False,full_parent_trace_disabled_to_bound_output_and_runtime=True,
        full_parent_RC_context_matrix_or_spatial_qualification_complete=False,
        new_opt_in_mode_adopted_as_physical_runtime_model=False)
    progress.update(observed_utc=datetime.now(timezone.utc).isoformat(),
        classification='RC_substrate_C_only_native_equivalence_validated_and_full_layout_raw_C_checks_running_not_release',
        evidence_sha256={str(p.relative_to(ROOT)):digest(p) for p in paths},RC_substrate_context_work=context,
        native_analog_jobs=analog,native_analog_count=len(analog),release_qualified=False,adopted=False,physical_whole_pll_passes=0,
        next_actions=[
            'Collect assembled-layout min/nom/max RC-substrate C extractions and attached feedback/network/zero-removal assessments under the original09:44UTC cutoff',
            'Compare native device identities and C corner coverage; retain old C-only context as separate diagnostic evidence',
            'Resolve bulk/well geometry,34 VGND internal supports, C/junction allocation and transient error before long native frequency work',
            'Obtain fresh qualified100/250/300/400MHz ranges/calibration; old invalid model cannot choose a redesign',
            'Complete frozen nominal15PVT timing/interfaces,60 physical wholePLL cases, ordered mode changes and remaining release gates'])
    snapshot=BASE/'qualification_progress_045.json';assert not snapshot.exists();write(snapshot,progress)
    overview=ROOT/'build/timing450/implementation_assessment.json';data=read(overview)
    data['latest_400mhz_qualification_progress']=str(snapshot.relative_to(ROOT));data['active_400mhz_RC_substrate_context_work']=context
    for key in ['release_qualified','selected','timing_closure_complete']:data[key]=False
    write(overview,data)
    print('Progress045: opt-in RC substrate context passes24 default+24 physical+3 DCO native comparisons; assembled-layout3-corner raw checks and assessments attached under original deadline. Release remains false.')


if __name__=='__main__':main()
