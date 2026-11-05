"""Review loaded pulse fixtures after preload settling; retain genuine short-pulse failures."""
import argparse
import json
from pathlib import Path
import time
from common_v3 import save,sha,verify
from resources import identity
from assess_prototype_native_waveform import crossings
from run_prototype_clock_pulse_routed_slew import waveform,assess,WIDTHS,LOADS


def settled_assessment(rows,kind,index,n):
    original=assess(rows,kind,index,n);old=int(kind=='low');new=1-old
    # The loaded SS rise has not settled at 4.5 ns. This later window is
    # still before the low-fixture D transition begins at 5.4 ns.
    pre=[r[index+1] for r in rows if 5e-9<=r[0]<=5.3e-9]
    good=bool(pre) and (min(pre)>=1.62 if old else max(pre)<=.18)
    edges=original['output_edges_ns']
    return dict(original_pre_state_verified=original['pre_state_verified'],pre_state_verified=good,
        pretest_window_ns=[5,5.3],final_state_verified=original['final_state_verified'],
        full_output_trace_capture_verified=good and original['final_state_verified'] and len(edges)==1 and edges[0]['direction']==('rise' if new else 'fall'),
        observed_clock_pulse_width_ps=original['observed_clock_pulse_width_ps'],output_edges_ns=edges)


def thresholds(records):
    if len(records)!=8 or {(r['kind'],r['nominal_width_ps']) for r in records}!={(k,w) for k in ('high','low') for w in WIDTHS}:raise ValueError('complete unique high/low width grid required')
    result={}
    for kind in ('high','low'):
        points=sorted((r for r in records if r['kind']==kind),key=lambda r:r['nominal_width_ps'])
        passing=[r['nominal_width_ps'] for i,r in enumerate(points) if all(p['full_output_trace_capture_verified'] for p in points[i:])]
        result[kind]=dict(smallest_tested_width_with_all_larger_samples_passing_ps=min(passing,default=None),
            failing_tested_widths_ps=[r['nominal_width_ps'] for r in points if not r['full_output_trace_capture_verified']],
            continuous_minimum_pulse_width_qualified=False)
    return result


def run(campaign,output):
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    while not (campaign/'assessment.json').exists():
        o=json.loads((campaign/'owner.json').read_text())
        if identity(o['pid'])!=o['birth']:raise ValueError('pulse campaign stopped without receipt')
        if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('pulse review deadline')
        time.sleep(1)
    rp=campaign/'assessment.json';r=json.loads(rp.read_text());verify(r['input_sha256']);verify(r['artifacts'])
    points=json.loads((campaign/'points.json').read_text());pins={str(p):sha(p) for p in (rp,campaign/'points.json',Path(__file__).resolve(),Path(__file__).with_name('run_prototype_clock_pulse_routed_slew.py'))};seen=set();results=[]
    for point in points:
        where=Path(point['directory']);receipt=where/'assessment.json';a=json.loads(receipt.read_text());verify(a['input_sha256']);verify(a['artifacts'])
        if point['assessment_sha256']!=sha(receipt):raise ValueError('pulse point receipt changed')
        if a['clock_full_ramp_ps']!=400:raise ValueError('400 ps clock-ramp fixture required')
        key=(point['corner'],point['master'])
        if key in seen:raise ValueError('duplicate pulse-grid point')
        seen.add(key);data=where/'waveform.dat';old=where/'observations.json'
        if a['artifacts'].get(str(data))!=sha(data) or a['artifacts'].get(str(old))!=sha(old):raise ValueError('unbound pulse-grid data')
        rows=waveform(data,8);declared=json.loads(old.read_text());observed=[]
        if [(x['kind'],x['nominal_width_ps']) for x in declared]!=[(k,w) for k in ('high','low') for w in WIDTHS]:raise ValueError('pulse case ordering changed')
        for i,case in enumerate(declared):
            baseline=assess(rows,case['kind'],i,8)
            if any(case[k]!=v for k,v in baseline.items()):raise ValueError('original pulse observations disagree')
            measured=settled_assessment(rows,case['kind'],i,8)
            if measured['observed_clock_pulse_width_ps'] is None or abs(measured['observed_clock_pulse_width_ps']-case['nominal_width_ps'])>1:raise ValueError('native clock pulse differs from intended width')
            for direction in (0,1):
                lo=crossings([(r[0],r[1+8+i]) for r in rows],.36)[direction]
                hi=crossings([(r[0],r[1+8+i]) for r in rows],1.44)[direction]
                if len(lo)!=len(hi) or not lo or any(abs(abs(a-b)*1e12-240)>1 for a,b in zip(lo,hi)):raise ValueError('measured clock slew differs from declared 20-to-80 interval')
            observed.append(dict(kind=case['kind'],nominal_width_ps=case['nominal_width_ps'],**measured))
        results.append(dict(corner=point['corner'],master=point['master'],cases=observed,sampled_thresholds=thresholds(observed)))
        pins.update({str(p):sha(p) for p in (receipt,data,old)})
    if seen!={(c,m) for c in ('tt','ff','ss','sf','fs') for m in LOADS}:raise ValueError('complete used-master five-corner pulse grid required')
    detail=output/'observations.json';save(detail,results);verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},native_cases=200,
        all_pretest_states_verified=all(c['pre_state_verified'] for r in results for c in r['cases']),
        actual_short_pulse_failures_retained=True,native_producer_observer_results_retained=True,clock_full_ramp_ps=400,measured_clock_slew_20_to_80_ps=240,
        all_grids_have_passing_high_and_low_samples=all(r['sampled_thresholds'][k]['smallest_tested_width_with_all_larger_samples_passing_ps'] is not None for r in results for k in ('high','low')),
        numerical_uncertainty_included=False,final_load_and_slew_envelope_verified=False,
        diagnostic=True,validated_for_prototype=False,release_ready=False))
    print('Reviewed pulse fixtures:',200)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--campaign',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args();run(a.campaign.resolve(),a.output.resolve())
