"""Correlate completed corrected corner captures and summarize observed phase response."""
import argparse
import json
from pathlib import Path
import time
from common_v3 import ROOT,PROFILE,spec,save,sha,verify
from resources import lease
from run_prototype_BBPD_coupled_pilot import read_table
from compare_prototype_BBPD_corrected_models import compare


def summarize(records):
    phases=[];delays=[];widths=[];latencies=[]
    for r in records:
        active=[n for n,v in r['outputs'].items() if v['detector_rising_edges_ns']]
        clean=len(active)==1 and all(v['one_toggle_per_detector_rise_observed'] and v['quiet_before_first_sample'] for v in r['outputs'].values())
        if clean:
            v=r['outputs'][active[0]];clean=len(v['detector_rising_edges_ns'])==len(v['detector_falling_edges_ns'])==2
        phases.append(dict(phase_ps=r['phase_ps'],observed_decision=active[0] if clean else 'ambiguous_or_uncaptured'))
        for v in r['outputs'].values():
            if v['paired_delays_ps'] is not None:delays+=v['paired_delays_ps']
            widths+=v['complete_high_pulse_widths_ps']
            if len(v['detector_rising_edges_ns'])==2:latencies += [(t-ref)*1000 for t,ref in zip(v['detector_rising_edges_ns'],(10.1,50.1))]
    phases.sort(key=lambda p:p['phase_ps']);dn=[r['phase_ps'] for r in phases if r['observed_decision']=='DN'];up=[r['phase_ps'] for r in phases if r['observed_decision']=='UP']
    monotone=all(r['observed_decision'] in ('DN','UP') for r in phases) and bool(dn and up) and max(dn)<min(up)
    if not delays or not widths or not latencies:raise ValueError('active native pulse/capture metrics required')
    return dict(decisions=phases,observed_single_polarity_transition=monotone,
        sampled_transition_bracket_ps=[max(dn),min(up)] if monotone else None,
        observed_detector_reference_delay_ps=[min(latencies),max(latencies)],observed_event_capture_delay_ps=[min(delays),max(delays)],
        observed_pulse_width_ps=[min(widths),max(widths)],qualified_uncertainty_bound=False)


def run(campaign,output):
    output.mkdir(parents=True,exist_ok=False)
    receipt=campaign/'assessment.json';r=json.loads(receipt.read_text());verify(r['input_sha256']);verify(r['artifacts'])
    if r['all_declared_native_phase_points_complete'] is not True or r['native_cases']!=67:raise ValueError('complete 67-case corrected native campaign required')
    points=campaign/'points.json';rows=json.loads(points.read_text())
    if rows['failures']:raise ValueError('native campaign failures remain')
    indexed={(x['corner'],x['geometry_model']):x for x in rows['results']}
    expected={(c,'signal') for c in spec()['corners']}|{(c,'full') for c in spec()['corners'] if c!='tt'}
    if len(indexed)!=9 or set(indexed)!=expected:raise ValueError('corner/model coverage mismatch')
    pins={str(p):sha(p) for p in (receipt,points,PROFILE,Path(__file__).resolve(),Path(__file__).with_name('compare_prototype_BBPD_corrected_models.py'),Path(__file__).with_name('run_prototype_BBPD_coupled_pilot.py'))}
    tt=ROOT/'build/signoff400/prototype_v3_BBPD_corrected_TT_model_comparison_001/assessment.json';tr=json.loads(tt.read_text());verify(tr['input_sha256']);verify(tr['artifacts']);pins[str(tt)]=sha(tt)
    if not tr['all_signal_threshold_crossing_counts_match'] or tr['compared_phase_cases']!=3:raise ValueError('reused TT native correlation incomplete')
    summaries={};comparisons=[]
    with lease(1,4,time.clock_gettime(time.CLOCK_BOOTTIME)+3600):
        for corner in spec()['corners']:
            native={}
            for kind in ('signal','full'):
                if (corner,kind) not in indexed:continue
                row=indexed[(corner,kind)];rp=Path(row['assessment'])
                if sha(rp)!=row['sha256']:raise ValueError('native point receipt changed')
                a=json.loads(rp.read_text());verify(a['input_sha256']);verify(a['artifacts'])
                obs=rp.parent/'observations.json';records=json.loads(obs.read_text())
                if records['failures']:raise ValueError('native point failures')
                pins.update({str(p):sha(p) for p in (rp,obs)});native[kind]=rp.parent
                if kind=='signal':summaries[corner]=summarize(records['results'])
            if corner=='tt':continue
            for phase in (-1000,0,1000):
                logs=[native[k]/('phase_'+str(phase)+'ps')/'native.log' for k in ('full','signal')]
                metrics=compare(*(read_table(p.read_text()) for p in logs));comparisons.append(dict(corner=corner,phase_ps=phase,signals=metrics))
                pins.update({str(p):sha(p) for p in logs})
    detail=output/'response_and_correlations.json';save(detail,dict(observed_phase_response=summaries,new_full_model_correlations=comparisons));verify(pins)
    matches=all(s['threshold_crossing_counts_match'] for r in comparisons for s in r['signals'].values())
    edges=[s['maximum_paired_edge_difference_ps'] for r in comparisons for s in r['signals'].values() if s['maximum_paired_edge_difference_ps'] is not None]
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},
        corrected_signal_cases=55,new_full_model_holdouts=12,reused_TT_full_holdouts=3,
        all_five_corner_full_model_crossing_counts_match=matches,maximum_observed_edge_difference_ps=max([tr['maximum_observed_edge_difference_ps'],*edges]),
        all_signal_grids_have_single_observed_transition=all(v['observed_single_polarity_transition'] for v in summaries.values()),
        native_bias_and_latency_observations_complete=True,reset_alignment_qualified=False,intercell_RC_included=False,parent_coupling_included=False,
        omitted_loads_bounded=False,numerical_error_proven_bounded=False,native_interface_qualified=False,diagnostic=True,validated_for_prototype=False,release_ready=False))
    print('Five-corner full-model crossing counts match:',matches)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--campaign',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run(a.campaign.resolve(),a.output.resolve())
