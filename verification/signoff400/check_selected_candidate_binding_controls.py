"""Exercise candidate-binding rejection using real receipts and isolated mutants."""
import argparse,json
from pathlib import Path
from common_v3 import save,sha,verify
from bind_selected_frozen_detector_candidate import bind


def run(prior,wrong_prior,comparison,protocol,fresh,bound,output):
    output.mkdir(parents=True,exist_ok=False)
    a=json.loads((bound/'assessment.json').read_text());verify(a['input_sha256']);verify(a['artifacts'])
    if not a['candidate_bytes_unchanged_since_prelaunch'] or a['parameters_refitted'] is not False:
        raise ValueError('unchanged positive bound candidate required')
    p=json.loads(protocol.read_text());verify(p['input_sha256'])
    for name in ['detector.v','parameters.json']:
        paths=[Path(x) for x in p['input_sha256'] if Path(x).name==name]
        if len(paths)!=1 or sha(bound/name)!=sha(paths[0]):raise ValueError('positive candidate copy differs from frozen bytes')
    bad_fresh=output/'failed_fresh.json';f=json.loads(fresh.read_text());f['all_event_counts_match']=False;save(bad_fresh,f)
    bad_protocol=output/'different_protocol.json';f=json.loads(protocol.read_text());f['created_boottime_s']+=1;save(bad_protocol,f)
    tests=[('wrong_corner_prior',wrong_prior,protocol,fresh,'same prior, candidate and validation operating point'),
           ('failed_independent_replay',prior,protocol,bad_fresh,'complete passing comparison and fresh sign/count/timing'),
           ('unbound_protocol',prior,bad_protocol,fresh,'fresh replay must bind identical prelaunch protocol')]
    records=[]
    for name,r,p,f,reason in tests:
        target=output/name
        try:bind(r,comparison,p,f,target)
        except ValueError as e:
            if reason not in str(e):raise
            if target.exists():raise ValueError('rejected binding created output')
            records.append(dict(control=name,rejected=True,reason=str(e),output_not_created=True))
        else:raise AssertionError('invalid binding accepted: '+name)
    files=[prior,wrong_prior,comparison,protocol,fresh,bound/'assessment.json',bad_fresh,bad_protocol,Path(__file__).resolve(),Path(__file__).with_name('bind_selected_frozen_detector_candidate.py')]
    save(output/'assessment.json',dict(input_sha256={str(x):sha(x)for x in files},positive_bound_candidate_matches_frozen_bytes=True,rejection_controls=records,controls_passed=3,native_simulations_launched=0,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['prior','wrong-prior','comparison','protocol','fresh','bound','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.prior.resolve(),a.wrong_prior.resolve(),a.comparison.resolve(),a.protocol.resolve(),a.fresh.resolve(),a.bound.resolve(),a.output.resolve())
