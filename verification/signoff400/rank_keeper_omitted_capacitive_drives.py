"""Rank omitted exterior voltage excursions by retained coupling-charge coefficient."""
import os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
import json,time
from fractions import Fraction
from pathlib import Path
import numpy as np
from common_v3 import ROOT,save,sha,verify
from resources import lease


def run():
    base=ROOT/'build/signoff400'
    waves=base/'selected_keeper_corrected_receiver_waveforms_1467'
    reduction=base/'selected_keeper_receiver_reduction_1420'
    roles=base/'selected_keeper_prescribed_boundary_roles_1522'
    output=base/'selected_keeper_omitted_capacitive_drives_1543'
    output.mkdir(exist_ok=False)
    os.sched_setaffinity(0,{31})
    receipts=[p/'assessment.json' for p in (waves,reduction,roles)]
    for p in receipts:
        record=json.loads(p.read_text());verify(record['input_sha256']);verify(record['artifacts'])
    role_file=roles/'boundaries.json';certificate=reduction/'charge_certificate.json';columns=waves/'columns.json'
    omitted={r['node'] for r in json.loads(role_file.read_text()) if r['kind']=='capacitive_only'}
    coefficients={}
    for group in json.loads(certificate.read_text())['groups']:
        for node,value in group['original_boundary_C_F_exact'].items():
            if node in omitted:coefficients[node]=coefficients.get(node,Fraction(0))+Fraction(value)
    data=np.load(waves/'boundary.npy',mmap_mode='r')
    names=json.loads(columns.read_text())['ordered_physical_ports']
    index={n:i+1 for i,n in enumerate(names)}
    with lease(1,8,time.clock_gettime(time.CLOCK_BOOTTIME)+3600):
        window=np.array(data[(data[:,0]>=200e-9)&(data[:,0]<=260e-9)],copy=True)
        if not len(window) or not np.isfinite(window).all():raise ValueError('finite complete final-window samples required')
        low=window.min(axis=0);high=window.max(axis=0)
        ranks=[]
        for node,c in coefficients.items():
            i=index[node];span=float(high[i]-low[i])
            ranks.append(dict(node=node,retained_C_F_exact=str(c),minimum_V=float(low[i]),maximum_V=float(high[i]),
                              excursion_charge_score_fC=float(c)*span*1e15))
        ranks.sort(key=lambda r:r['excursion_charge_score_fC'],reverse=True)
    rank_file=output/'ranking.json';save(rank_file,ranks)
    files=[*receipts,role_file,certificate,columns,Path(__file__).resolve()]
    save(output/'assessment.json',dict(input_sha256={str(p):sha(p) for p in files},artifacts={str(rank_file):sha(rank_file)},
         completed_reference_only=True,window_ns=[200,260],samples=len(window),
         capacitive_only_boundaries_with_retained_coupling=len(coefficients),
         retained_C_F_exact=str(sum(coefficients.values(),Fraction(0))),
         score_definition='sum retained coupling C times sampled exterior voltage span',
         score_is_not_frequency_error_bound=True,phase_and_cancellation_ignored=True,
         changed_controller_prediction_qualified=False,model_qualified=False,release_ready=False))


if __name__=='__main__':run()
