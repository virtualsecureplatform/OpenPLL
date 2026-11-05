"""Wait for the changed solver/tolerance run and compare full-cycle observations; qualify no error bound."""
import argparse
import json
import math
import os
from pathlib import Path
import time
from common_v3 import ROOT,save,sha,verify
from resources import identity
from assess_prototype_native_waveform import run as assess
from compare_prototype_numerical_holdout import load
from compare_prototype_DCO_native_decks import compare as compare_decks


def compare_metrics(a,b):
    for key in ('corner','temperature_c','supply_v','coarse_code','fine_code','measurement_start_s','measurement_end_s'):
        if a[key]!=b[key]:raise ValueError('native operating point/window mismatch: '+key)
    for r in (a,b):
        if r['complete_measured_cycles']<4:raise ValueError('insufficient complete native cycles')
        lo,hi=r['observed_frequency_interval_hz'];mean=r['average_frequency_hz']
        if not all(math.isfinite(v) for v in (lo,hi,mean)) or not 0<lo<=mean<=hi:raise ValueError('invalid measured frequency interval/mean')
    delta=abs(a['average_frequency_hz']-b['average_frequency_hz'])
    return dict(mean_frequency_hz=[a['average_frequency_hz'],b['average_frequency_hz']],
        observed_mean_difference_hz=delta,observed_mean_difference_ppm=delta/a['average_frequency_hz']*1e6,
        observed_frequency_envelope_hz=[min(r['observed_frequency_interval_hz'][0] for r in (a,b)),max(r['observed_frequency_interval_hz'][1] for r in (a,b))],
        observed_duty_envelope=[min(r['observed_duty_interval'][0] for r in (a,b)),max(r['observed_duty_interval'][1] for r in (a,b))],
        observed_fastest_startup_frequency_hz=max(r['fastest_observed_frequency_including_startup_hz'] for r in (a,b)),
        solver_and_abstol_changed_together=True,solver_and_tolerance_effects_independently_separated=False,
        numerical_error_proven_bounded=False,numerical_convergence_qualified=False,functional_capture_margin_evaluated=False)


def run(baseline,alternative,output):
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline))
    save(output/'status.json',dict(state='waiting_for_alternative_native_run',release_ready=False))
    while True:
        owner=json.loads((alternative/'owner.json').read_text());status=json.loads((alternative/'status.json').read_text())
        live=identity(owner['pid'])==owner['birth']
        if status['state']=='stopped_without_promotion':raise ValueError('alternative native run failed; no numerical comparison')
        if not live:
            if not (alternative/'assessment.json').exists():raise ValueError('alternative native owner disappeared without receipt')
            break
        if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('solver waveform review deadline')
        time.sleep(2)
    source_identity=ROOT/'build/signoff400/prototype_v3_KLU_device_source_identity_001/assessment.json'
    regression=ROOT/'build/signoff400/prototype_v3_KLU_capture_comparison_001/assessment.json'
    sr,rr=[json.loads(p.read_text()) for p in (source_identity,regression)]
    for r in (sr,rr):verify(r['input_sha256']);verify(r['artifacts'])
    if sr.get('all_device_model_sources_byte_identical') is not True or sr['device_source_files']!=1212:raise ValueError('matching stock compact-device sources required')
    if rr['cases']!=21 or rr['outcome_or_crossing_count_differences']!=0:raise ValueError('native KLU receiver regression required')
    alt=output/'alternative_waveform_review';assess(alternative,alt)
    a,ac,ap=load(baseline);b,bc,bp=load(alt)
    def deck_path(paths):
        receipt=json.loads(paths[0].read_text())
        files=[Path(p) for p in receipt['input_sha256'] if Path(p).name.startswith('dco_postlayout_') and p.endswith('.spice')]
        if len(files)!=1:raise ValueError('one reviewed native generated deck required')
        return files[0]
    ad,bd=deck_path(ap),deck_path(bp)
    decks,normalized=compare_decks(ad.read_text(),bd.read_text());comparison=compare_metrics(a,b)
    paths=[*ap,*bp,ad,bd,source_identity,regression,Path(__file__).resolve(),Path(__file__).with_name('compare_prototype_DCO_native_decks.py'),Path(__file__).with_name('compare_prototype_numerical_holdout.py')]
    pins={str(p):sha(p) for p in paths};detail=output/'comparison.json';save(detail,dict(deck_identity=decks,waveforms=comparison));verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},
        full_cycle_solver_tolerance_observations_compared=True,numerical_error_proven_bounded=False,
        diagnostic=True,validated_for_prototype=False,release_ready=False))
    save(output/'status.json',dict(state='solver_waveform_review_terminal',release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('baseline','alternative','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(a.baseline.resolve(),a.alternative.resolve(),a.output.resolve())
