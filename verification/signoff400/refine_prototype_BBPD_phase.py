"""Refine observed phase-transition brackets adaptively; unresolved probes retain their enclosing bracket."""
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from common_v3 import ROOT,PROFILE,spec,save,sha,verify
from resources import identity


def decision(record):
    active=[name for name,r in record['outputs'].items() if r['detector_rising_edges_ns']]
    if len(active)!=1:return None
    if any(not r['one_toggle_per_detector_rise_observed'] or not r['quiet_before_first_sample'] for r in record['outputs'].values()):return None
    r=record['outputs'][active[0]]
    return active[0] if len(r['detector_rising_edges_ns'])==len(r['detector_falling_edges_ns'])==2 else None


def run(review,output):
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    receipt=review/'assessment.json';r=json.loads(receipt.read_text());verify(r['input_sha256']);verify(r['artifacts'])
    if not r['all_signal_grids_have_single_observed_transition'] or not r['all_five_corner_full_model_crossing_counts_match']:raise ValueError('complete observed five-corner brackets/correlation required')
    response=review/'response_and_correlations.json';data=json.loads(response.read_text())['observed_phase_response']
    worker=Path(__file__).with_name('run_prototype_BBPD_phase_probe.py')
    pins={str(p):sha(p) for p in (receipt,response,PROFILE,worker,Path(__file__).resolve())}
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,max_small_native_workers=4,automatic_identical_retry=False))
    save(output/'input_manifest.json',dict(input_sha256=pins,initial_brackets_ps={c:data[c]['sampled_transition_bracket_ps'] for c in spec()['corners']},target_observation_width_ps=25,max_refinements_per_corner=4,
        interpretation='Sampled nominal transition interval; not a universal phase-error or loading bound.'))
    results=[];failures=[]
    def corner(c):
        folder=output/c;folder.mkdir();lo,hi=data[c]['sampled_transition_bracket_ps'];observations=[];seen={p['phase_ps'] for p in data[c]['decisions']}
        if not lo<hi:raise ValueError('ordered native bracket required')
        for i in range(4):
            if hi-lo<=25:break
            mid=(lo+hi)//2
            if mid in seen or not lo<mid<hi:raise ValueError('phase refinement would duplicate/outgrow prior observations')
            seen.add(mid);point=folder/('step'+str(i)+'_phase'+str(mid));log=folder/(point.name+'.log')
            command=[sys.executable,str(worker),'--geometry-model','signal','--corner',c,'--phases-ps',str(mid),'--output',str(point)]
            remaining=deadline-time.clock_gettime(time.CLOCK_BOOTTIME)
            if remaining<=0:raise TimeoutError('phase-refinement deadline')
            with log.open('x') as stream:code=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT,timeout=remaining).returncode
            if code:raise ValueError('native phase probe controller failed')
            rp=point/'assessment.json';pr=json.loads(rp.read_text());verify(pr['input_sha256']);verify(pr['artifacts'])
            obs=json.loads((point/'observations.json').read_text());choice=None
            if pr['completed_cases']==1 and pr['all_declared_native_waveforms_complete'] and not obs['failures']:
                if len(obs['results'])!=1 or obs['results'][0]['phase_ps']!=mid:raise ValueError('native refinement phase mismatch')
                choice=decision(obs['results'][0])
            observations.append(dict(phase_ps=mid,observed_decision=choice,assessment=str(rp),sha256=sha(rp),enclosing_bracket_before_ps=[lo,hi],native_failures=obs['failures']))
            if choice=='DN':lo=mid
            elif choice=='UP':hi=mid
            else:break
        result=dict(corner=c,observed_transition_bracket_ps=[lo,hi],target_width_reached=hi-lo<=25,observations=observations,
            unresolved_probe_retains_enclosing_bracket=any(p['observed_decision'] is None for p in observations),qualified_uncertainty_bound=False)
        save(folder/'result.json',result);return result
    save(output/'status.json',dict(state='native_phase_refinement_running',completed_corners=0,failed_corners=0,release_ready=False))
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures={pool.submit(corner,c):c for c in spec()['corners']}
        for future in as_completed(futures):
            try:results.append(future.result())
            except Exception as exc:failures.append(dict(corner=futures[future],reason=repr(exc)))
            save(output/'status.json',dict(state='native_phase_refinement_running',completed_corners=len(results),failed_corners=len(failures),release_ready=False))
    verify(pins);detail=output/'corners.json';save(detail,dict(results=results,failures=failures))
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},completed_corners=len(results),
        all_observed_brackets_refined_to_25ps=len(results)==5 and not failures and all(r['target_width_reached'] for r in results),
        native_probe_cases=sum(len(r['observations']) for r in results),parent_coupling_included=False,intercell_RC_included=False,omitted_loads_bounded=False,
        qualified_uncertainty_bound=False,native_interface_qualified=False,diagnostic=True,validated_for_prototype=False,release_ready=False))
    save(output/'status.json',dict(state='native_phase_refinement_terminal',completed_corners=len(results),failed_corners=len(failures),release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--review',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run(a.review.resolve(),a.output.resolve())
