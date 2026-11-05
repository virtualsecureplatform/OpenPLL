"""Prepare an explicitly unqualified closed-loop diagnostic from native endpoint observations."""
import argparse
from fractions import Fraction as F
import json
from pathlib import Path
from common_v3 import ROOT,PROFILE,source_pins,save,sha,verify


def interpolate_period(a,b):
    lo,hi=a['fine_code'],b['fine_code']
    if not 8<=lo<hi<=247 or (a['corner'],a['coarse_code'])!=(b['corner'],b['coarse_code']):raise ValueError('matched safe-code native interpolation endpoints required')
    fa,fb=F(str(a['average_frequency_hz'])),F(str(b['average_frequency_hz']))
    if fa<=0 or fb<=0:raise ValueError('positive native frequencies required')
    return {code:1/((1-F(code-lo,hi-lo))/fa+F(code-lo,hi-lo)/fb) for code in range(lo,hi+1)}


def run(left,right,detector_fit,replay,seed,output):
    paths=[];points=[]
    for directory in (left,right):
        receipt=directory/'all_cycle_assessment/assessment.json';r=json.loads(receipt.read_text());verify(r['input_sha256']);verify(r['artifacts'])
        file=receipt.parent/'all_cycle_metrics.json'
        if not r['all_captured_measurement_cycles_assessed'] or r['artifacts'].get(str(file))!=sha(file):raise ValueError('complete pinned all-cycle endpoints required')
        points.append(json.loads(file.read_text()));paths.extend((receipt,file))
    a,b=sorted(points,key=lambda r:r['fine_code']);table=interpolate_period(a,b)
    if not a['fine_code']<seed<b['fine_code'] or not min(a['average_frequency_hz'],b['average_frequency_hz'])<400e6<max(a['average_frequency_hz'],b['average_frequency_hz']):raise ValueError('interior seed and observed target bracket required')
    corner=a['corner'];fit_receipt=detector_fit/'assessment.json';fr=json.loads(fit_receipt.read_text());verify(fr['input_sha256']);verify(fr['artifacts'])
    rr=replay/'assessment.json';r=json.loads(rr.read_text());verify(r['input_sha256']);verify(r['artifacts'])
    if not r['all_fit_event_counts_match'] or not r['all_fit_edges_within_observed_band']:raise ValueError('compiled detector fitting-point replay required')
    model=detector_fit/corner/'detector.v';parameters=detector_fit/corner/'parameters.json'
    if fr['artifacts'].get(str(model))!=sha(model) or r['input_sha256'].get(str(model))!=sha(model):raise ValueError('replayed matching detector model required')
    paths.extend((fit_receipt,rr,model,parameters,PROFILE,Path(__file__).resolve()))
    pins={str(p):sha(p) for p in paths};pins.update(source_pins());verify(fr['candidate']['physical_sha256'])
    output.mkdir(parents=True,exist_ok=False);dco=output/'dco_table.txt'
    # Never extrapolate an unmeasured code. A code outside this supported range
    # must fail MODEL_LOOKUP_MISSING rather than silently invent a frequency.
    dco.write_text(''.join(f"{a['coarse_code']} {code} {round(frequency*1000)}\n" for code,frequency in table.items()))
    provenance=output/'interpolation.json';save(provenance,dict(method='linear_period_between_native_endpoints',
        endpoints=[a,b],interior_native_holdouts_verified=False,final_loading_complete=False,
        uncertainty_included=False,diagnostic=True,synthetic=True,release_ready=False))
    pins.update({str(p):sha(p) for p in (dco,provenance)});verify(pins)
    save(output/'models.json',dict(corner=corner,temperature_c=27,supply_v=1.8,profile_sha256=sha(PROFILE),
        synthetic=True,model_kind='unqualified_native_measurement_fit_and_period_interpolation',
        candidate_source_sha256=source_pins(),candidate_physical_sha256=fr['candidate']['physical_sha256'],
        input_sha256=pins,dco_table=str(dco),detector_rtl=str(model),coarse=a['coarse_code'],seed=seed,
        polarity=int(b['average_frequency_hz']>a['average_frequency_hz']),
        physical_models_qualified=False,release_ready=False))
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in (output/'models.json',provenance,dco)},
        diagnostic=True,synthetic=True,validated_for_prototype=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--left',type=Path,required=True);p.add_argument('--right',type=Path,required=True);p.add_argument('--detector-fit',type=Path,required=True);p.add_argument('--replay',type=Path,required=True);p.add_argument('--seed',type=int,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.left.resolve(),a.right.resolve(),a.detector_fit.resolve(),a.replay.resolve(),a.seed,a.output.resolve())
