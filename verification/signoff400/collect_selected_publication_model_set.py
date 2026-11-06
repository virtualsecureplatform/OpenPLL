"""Collect complete frozen publication models for all five prototype corners.

Completeness does not qualify uncertainty, controller timing, or correlation.
"""
import argparse,json,math
from pathlib import Path
from common_v3 import save,sha,verify


def run(models,output):
    if output.exists():raise FileExistsError(output)
    pins={str(Path(__file__).resolve()):sha(Path(__file__))};records={};physical=None
    for model in models:
        params=model/'parameters.json';receipt=model/'assessment.json'
        p=json.loads(params.read_text());a=json.loads(receipt.read_text())
        verify(a['input_sha256']);verify(a['artifacts'])
        if a['artifacts'].get(str(params))!=sha(params):raise ValueError('parameters must be bound by original measured assessment')
        op=p['operating_point'];corner=op['corner']
        if corner not in ['tt','ff','ss','sf','fs'] or corner in records or op['temperature_c']!=27 or op['supply_v']!=1.8:raise ValueError('unique supported operating points required')
        if p['missing_directions'] or set(p['publication_delays'])!={'up','dn'}:raise ValueError('all four directions required; fallback prohibited')
        if physical is None:physical=p['native_model_sha256']
        if physical!=p['native_model_sha256']:raise ValueError('same selected native physical model required')
        verify(p['native_model_sha256']);delays={}
        for role in ['up','dn']:
            if set(p['publication_delays'][role])!={'rise','fall'}:raise ValueError('both transition directions required')
            delays[role]={}
            for edge in ['rise','fall']:
                r=p['publication_delays'][role][edge];v=r['nominal_ns'];lo,hi=r['observed_interval_ns']
                if not all(math.isfinite(x) for x in [v,lo,hi]) or not 0<lo<=v<=hi or type(r['samples']) is not int or r['samples']<1:raise ValueError('finite measured positive publication delays required')
                delays[role][edge]=dict(nominal_ps=1000*v,observed_interval_ps=[1000*lo,1000*hi],samples=r['samples'])
        pins.update({str(f):sha(f) for f in [params,receipt]})
        records[corner]=dict(model=str(model),training_cases=p['training_cases'],publication_delays=delays)
    if set(records)!={'tt','ff','ss','sf','fs'}:raise ValueError('exactly all five corners required')
    verify(pins)
    save(output,dict(input_sha256=pins,records=records,native_physical_model_sha256=physical,all_twenty_directions_measured=True,missing_direction_fallback_permitted=False,scope='retained publication/first-stage receiver with recorded TT upstream excitation and requested-corner devices',observed_intervals_are_not_uniform_uncertainty_bounds=True,uniform_uncertainty_bound_qualified=False,complete_controller_timing_qualified=False,release_ready=False))
    print('collected 20 measured directions across five corners')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--model',type=Path,action='append',required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run([m.resolve() for m in a.model],a.output.resolve())
