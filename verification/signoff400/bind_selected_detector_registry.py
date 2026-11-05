"""Bind a selected-layout diagnostic detector without invalidating analog cache.

The new registry remains diagnostic; observed holdout agreement is never
promoted to prototype qualification or complete physical interface coverage.
"""
import argparse,json
from pathlib import Path
from common_v3 import save,sha,verify
from selected_model_registry import create,validate
from selected_clock_timing import load


def run(base,fit,clock_timing,output):
    if output.exists():raise FileExistsError(output)
    old=validate(json.loads(base.read_text()));receipt=fit/'assessment.json';a=json.loads(receipt.read_text())
    verify(a['input_sha256']);verify(a['artifacts'])
    if a.get('status')!='conditional_selected_detector_fit' or a.get('diagnostic') is not True or a.get('validated_for_prototype') is not False or a.get('release_ready') is not False:raise ValueError('explicitly unqualified selected detector fit required')
    if not all(a.get(k) is True for k in ['all_sampled_signs_match','all_event_counts_match','all_edges_within_observed_fit_band']):raise ValueError('sampled diagnostic model replay did not agree')
    op=old['analog']['operating_point']
    if any(a.get(k)!=op[k] for k in ['corner','temperature_c','supply_v']):raise ValueError('detector/analog operating point mismatch')
    if not a.get('native_model_sha256') or any(old['analog']['input_sha256'].get(p)!=d for p,d in a['native_model_sha256'].items()):raise ValueError('detector/analog physical model mismatch')
    load(clock_timing,old)
    model=fit/'detector.v';parameters=fit/'parameters.json'
    if any(a['artifacts'].get(str(p))!=sha(p) for p in [model,parameters]):raise ValueError('fitted model and parameter artifacts required')
    interface=dict(input_sha256={str(p):sha(p) for p in [receipt,model,parameters,clock_timing]},
        detector_rtl=str(model),clock_timing=str(clock_timing),selected_layout_timing_qualified=False,
        source_scope=a['scope'],native_interface_qualified=False,full_phase_coverage_qualified=False,
        receiver_path_latency_included=False,exterior_switching_qualified=False)
    output.mkdir(parents=True)
    value=create(old['analog'],interface,[Path(p['receipt']) for p in old['points']],output/'models.json')
    if value['analog_key']!=old['analog_key'] or value['interface_key']==old['interface_key']:raise ValueError('analog cache must remain unchanged and detector identity must advance')
    pins={str(p):sha(p) for p in [base,receipt,clock_timing,Path(__file__).resolve(),Path(__file__).with_name('selected_model_registry.py'),Path(__file__).with_name('selected_clock_timing.py')]};verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(output/'models.json'):sha(output/'models.json')},
        analog_cache_key_unchanged=True,interface_cache_key_changed=True,measured_points_retained=len(value['points']),
        diagnostic=True,physical_models_qualified=False,release_ready=False))
    print(json.dumps(dict(analog_cache_key_unchanged=True,measured_points_retained=len(value['points']),interface_key=value['interface_key'])))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['base','fit','clock-timing','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n.replace('-','_')).resolve() for n in ['base','fit','clock-timing','output']))
