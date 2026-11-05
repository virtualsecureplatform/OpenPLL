"""Report saved-sample logic agreement without inventing a voltage release gate.

The 0.9 V threshold is the existing edge/readback convention. This does not
establish noise margins, unsaved hazards, cell timing, or model qualification.
"""
import argparse,json
from pathlib import Path
import numpy as np
from common_v3 import save,sha,verify
from compare_selected_streaming import read


def assess(reference,candidate,threshold=.9):
    rn,r=read(reference);cn,c=read(candidate)
    if not np.isfinite(threshold):raise ValueError('finite logic threshold required')
    if r[0,0]>c[0,0] or r[-1,0]<c[-1,0]:raise ValueError('reference must cover every observation')
    if len(set(rn))!=len(rn) or len(set(cn))!=len(cn):raise ValueError('unique channel inventory required')
    metrics={}
    for j,name in enumerate(cn[1:],1):
        key=name if name in rn else 'v(xpll:'+name[2:]
        if key not in rn:raise ValueError('missing native observation channel: '+name)
        rv=np.interp(c[:,0],r[:,0],r[:,rn.index(key)]);cv=c[:,j]
        mismatch=(rv>=threshold)!=(cv>=threshold)
        worst=float(np.max(np.abs(rv-cv)))
        margin=float(np.min(np.abs(rv-threshold)))
        metrics[name]=dict(observations=len(cv),sampled_logic_mismatches=int(np.count_nonzero(mismatch)),
            maximum_voltage_difference_V=worst,minimum_native_sample_distance_to_threshold_V=margin,
            minimum_candidate_sample_distance_to_threshold_V=float(np.min(np.abs(cv-threshold))),
            all_native_sample_distances_exceed_global_channel_error=margin>worst)
    if not metrics:raise ValueError('observation channels required')
    return dict(first_observation_s=float(c[0,0]),last_observation_s=float(c[-1,0]),
        samples=len(c),channels=len(metrics),logic_threshold_V=threshold,
        sampled_logic_mismatches=sum(m['sampled_logic_mismatches'] for m in metrics.values()),
        saved_sample_logic_agreement=all(m['sampled_logic_mismatches']==0 for m in metrics.values()),
        metrics=metrics,unsaved_hazards_assessed=False,native_cell_timing_qualified=False,
        physical_correlation_qualified=False,release_ready=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['reference','candidate','comparison','output']:p.add_argument('--'+key,required=True,type=Path)
    a=p.parse_args()
    if a.output.exists():p.error('fresh output required')
    prior=json.loads(a.comparison.read_text());verify(prior['input_sha256'])
    for path in [a.reference,a.candidate]:
        if prior['input_sha256'].get(str(path.resolve()))!=sha(path):raise ValueError('observation inputs must match completed comparison')
    pins={str(x.resolve()):sha(x) for x in [a.reference,a.candidate,a.comparison,Path(__file__),Path(__file__).with_name('compare_selected_streaming.py')]}
    value=assess(a.reference,a.candidate)
    if prior['end_s']!=value['last_observation_s'] or prior['channels']!=value['channels'] or prior['candidate_samples']!=value['samples']:
        raise ValueError('completed comparison inventory must match observations')
    verify(pins);value['input_sha256']=pins;save(a.output,value)
    print(json.dumps({k:v for k,v in value.items() if k not in ['metrics','input_sha256']}))
