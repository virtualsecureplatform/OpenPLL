#!/usr/bin/env python3
"""Reconcile completed check handles without retaining inherited running snapshots.

Close this bounded CAD/assessment phase only. RC runtime eligibility, physical
PLL timing and all frozen release gates remain unfulfilled. Preserve historical
process observations separately from current verified terminal state.
"""
from datetime import datetime,timezone
from pathlib import Path
import time
from record_qualification_progress_031 import ROOT,BASE,read,digest,write
from record_qualification_progress_045 import process


def main():
    prior_path=BASE/'qualification_progress_047.json';prior=read(prior_path);jobs=[]
    paths=[Path(__file__).resolve(),prior_path,ROOT/'verification/release_requirements_400mhz.json',ROOT/'verification/release_plan_400mhz.json']
    assert digest(paths[-2])=='02911569a2538d8b4d6c3139decdf7ec4d7c33bf2cbad85eed442947c0022b52'
    assert digest(paths[-1])=='2d6d5ed4404df842d64d42d68ebe593e4f627e65b4f90aaa48bef5f991e94b02'
    deadline=3136114.566309955;assert time.clock_gettime(time.CLOCK_BOOTTIME)<deadline
    roots=[('source','poly_metal_full_RC_substrate_capacitance_001','raw_network_terminal'),
        ('assessment','RC_substrate_capacitance_collection_002','RC_substrate_network_assessments_terminal'),
        ('comparison','RC_substrate_C_context_matrix_comparison_001','canonical_C_comparison_terminal'),
        ('differences','RC_substrate_C_context_matrix_difference_001','exact_matrix_difference_terminal')]
    for corner in ['min','nom','max']:
        states={}
        for label,root,terminal in roots:
            directory=BASE/root/corner;state=read(directory/'status.json');owner=read(directory/'owner.json')
            assert state['state']==terminal and owner['deadline_uptime']==deadline
            runner=process(owner['runner_pid']);assert not runner['live'],(directory,runner)
            states[label]=dict(directory=str(directory.relative_to(ROOT)),state=state['state'],runner=runner)
            paths.extend([directory/'status.json',directory/'owner.json'])
        jobs.append(dict(corner=corner,all_handles_terminal=True,stages=states))
    inventory=BASE/'DCO_C_R_support_inventory_001/status.json';assert read(inventory)['state']=='C_R_support_inventory_terminal';paths.append(inventory)
    support=prior['C_to_R_support_inventory'];assert support['missing_conductor_names']=={}
    known=[p for p in Path('/proc').glob('[0-9]*')]
    engines=[]
    for p in known:
        try:
            name=(p/'comm').read_text().strip()
            if name not in ['Xyce','ngspice','magicdnull']:continue
            r=process(int(p.name))
            if r['live']:engines.append(dict(kind=name,**r))
        except (FileNotFoundError,ProcessLookupError):continue
    assert not engines,engines
    progress=dict(prior);now=datetime.now(timezone.utc).isoformat()
    progress.update(observed_utc=now,classification='common_substrate_C_check_closed_with_all_handles_terminal_not_release',
        evidence_sha256={str(p.relative_to(ROOT)):digest(p) for p in paths},
        historical_full_RC_C_job_observations=prior.get('current_full_RC_C_jobs',[]),current_full_RC_C_jobs=jobs,
        native_analog_jobs=[],native_analog_count=0,current_native_CAD_and_analog_engines=[],
        scoped_common_substrate_C_check=dict(terminal_before_original_deadline=True,deadline_uptime=deadline,
            closed_utc=now,original_budget_not_restarted=True,all_three_native_C_and_assessment_stages_complete=True,
            all_three_exact_matrix_comparison_and_difference_stages_complete=True,all_source_and_assessment_handles_terminal=True,
            this_is_not_whole_PLL_or_runtime_model_qualification=True),release_qualified=False,adopted=False,physical_whole_pll_passes=0)
    context=dict(progress['RC_substrate_context_work'])
    context['historical_raw_C_job_observations']=context.get('assembled_layout_raw_C_jobs',[])
    context['assembled_layout_raw_C_jobs']=jobs;context['all_full_C_handles_verified_terminal']=True
    progress['RC_substrate_context_work']=context
    progress['next_actions']=[
        'Construct a geometry-consistent distributed C/junction model;43.835um nearest-representative gaps prohibit naive nearest-node placement',
        'Address resistor segment support, intrinsic resistor body C, local junction allocation and body connections at supply origins; quantify transient error',
        'Any next model-qualification check must use changed implementation/inputs, include its preparation and assessment in a12h budget, and never retry identical failed native jobs',
        'After a fresh runtime model is eligible, obtain nominal15PVT100/250/300/400 ranges/calibration/reset reachability and choose among isolated design candidates',
        'Complete all frozen timing/interface,60 physical wholePLL, ordered mode-change, supply/noise, jitter/power/area and integration release gates']
    snapshot=BASE/'qualification_progress_048.json';assert not snapshot.exists();write(snapshot,progress)
    overview=ROOT/'build/timing450/implementation_assessment.json';data=read(overview)
    data['latest_400mhz_qualification_progress']=str(snapshot.relative_to(ROOT))
    data['active_400mhz_RC_substrate_context_work']=context;data['active_400mhz_common_substrate_C_check_closeout']=progress['scoped_common_substrate_C_check']
    for key in ['release_qualified','selected','timing_closure_complete']:data[key]=False
    write(overview,data)
    print('Progress048: this common-substrate C check closed before its original12h cutoff; all handles terminal, no native engines live. Physical runtime/timing/release qualification remains incomplete.')


if __name__=='__main__':main()
