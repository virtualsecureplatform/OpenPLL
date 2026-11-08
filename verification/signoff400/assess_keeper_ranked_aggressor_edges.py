"""Record threshold crossings of ranked omitted aggressors in a completed reference."""
import os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
import json,time
from pathlib import Path
import numpy as np
from common_v3 import ROOT,save,sha,verify
from resources import lease
from assess_selected_detector_phase_probe_v2 import transitions


def run():
    base=ROOT/'build/signoff400'
    waves=base/'selected_keeper_corrected_receiver_waveforms_1467'
    ranking=base/'selected_keeper_omitted_capacitive_drives_1543'
    output=base/'selected_keeper_ranked_aggressor_edges_1546'
    output.mkdir(exist_ok=False)
    os.sched_setaffinity(0,{30})
    receipts=[p/'assessment.json' for p in (waves,ranking)]
    for receipt in receipts:
        r=json.loads(receipt.read_text());verify(r['input_sha256']);verify(r['artifacts'])
    ranks=json.loads((ranking/'ranking.json').read_text())[:20]
    names=json.loads((waves/'columns.json').read_text())['ordered_physical_ports']
    index={n:i+1 for i,n in enumerate(names)}
    with lease(1,8,time.clock_gettime(time.CLOCK_BOOTTIME)+3600):
        data=np.load(waves/'boundary.npy',mmap_mode='r')
        selected=np.flatnonzero((data[:,0]>=200e-9)&(data[:,0]<=260e-9))
        results=[]
        for rank in ranks:
            node=rank['node']
            rows=np.array(data[np.ix_(selected,[0,index[node]])]).tolist()
            edges=transitions(rows,1)
            periods=np.diff(edges['rising_ns'])
            # Report crossing intervals without assuming these are periodic clocks.
            results.append(dict(node=node,excursion_charge_score_fC=rank['excursion_charge_score_fC'],
                 crossings=edges,rises=len(edges['rising_ns']),falls=len(edges['falling_ns']),
                 minimum_rising_interval_ns=float(periods.min()) if len(periods) else None,
                 maximum_rising_interval_ns=float(periods.max()) if len(periods) else None))
    artifact=output/'edges.json';save(artifact,results)
    files=[*receipts,Path(__file__).resolve(),Path(__file__).with_name('assess_selected_detector_phase_probe_v2.py')]
    save(output/'assessment.json',dict(input_sha256={str(p):sha(p) for p in files},artifacts={str(artifact):sha(artifact)},
         completed_reference_only=True,ranked_boundaries=20,window_ns=[200,260],threshold_V=0.9,
         edge_counts_do_not_establish_periodic_clock_models=True,
         causal_aggressor_models_qualified=False,frequency_effect_qualified=False,release_ready=False))


if __name__=='__main__':run()
