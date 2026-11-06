"""Characterize noiseless native clock timing variation without a jitter limit.

These finite-window metrics include deterministic startup drift and numerical
variation. No thermal/flicker-noise or precision phase-noise qualification follows.
"""
import argparse,csv,json,math,statistics
from pathlib import Path
from common_v3 import save,sha,verify
from selected_spice_device_conditions import reference_deck,read


def statistics_from_edges(edges):
    if len(edges)<4 or any(not math.isfinite(t)for t in edges)or any(a>=b for a,b in zip(edges,edges[1:])):raise ValueError('at least four strictly ordered finite rising edges required')
    relative=[t-edges[0]for t in edges];periods=[b-a for a,b in zip(relative,relative[1:])];mean=statistics.fmean(periods)
    rms=lambda values:math.sqrt(statistics.fmean(x*x for x in values))
    count=len(relative);center=(count-1)/2;average=statistics.fmean(relative);indices=[i-center for i in range(count)]
    fitted_period=sum(i*(t-average)for i,t in zip(indices,relative))/sum(i*i for i in indices)
    tie=[t-average-fitted_period*i for i,t in zip(indices,relative)]
    mid=[(a+b)/2 for a,b in zip(relative,relative[1:])];midcenter=statistics.fmean(mid);den=sum((x-midcenter)**2 for x in mid);drift=sum((x-midcenter)*(p-mean)for x,p in zip(mid,periods))/den
    detrended=[p-mean-drift*(x-midcenter)for x,p in zip(mid,periods)]
    return dict(rising_edges=count,complete_periods=len(periods),mean_frequency_MHz=1000/mean,mean_period_ns=mean,
        sampled_period_min_max_ns=[min(periods),max(periods)],sampled_period_peak_to_peak_ps=1000*(max(periods)-min(periods)),
        sampled_period_RMS_deviation_ps=1000*rms([p-mean for p in periods]),sampled_cycle_to_cycle_RMS_ps=1000*rms([b-a for a,b in zip(periods,periods[1:])]),
        linear_period_drift_ps_per_ns=1000*drift,detrended_sampled_period_RMS_ps=1000*rms(detrended),
        best_fit_edge_period_ns=fitted_period,detrended_sampled_TIE_RMS_ps=1000*rms(tie),detrended_sampled_TIE_peak_to_peak_ps=1000*(max(tie)-min(tie)))


def run(provenance_path,output,start_ns=200,end_ns=260):
    if output.exists():raise FileExistsError(output)
    if not 0<=start_ns<end_ns<=260:raise ValueError('window inside complete 260 ns native horizon required')
    p=json.loads(provenance_path.read_text());verify(p['input_sha256']);verify(p['artifacts'])
    signals=provenance_path.parent/'signals.csv';assessment=provenance_path.parent/'assessment.json';a=json.loads(assessment.read_text())
    for path in(signals,assessment):
        if p['artifacts'].get(str(path))!=sha(path):raise ValueError('waveform and assessment must share native provenance')
    if a['end_ns']!=260 or len(a['coarse_code']['window_codes'])!=1 or len(a['dco_code']['window_codes'])!=1:raise ValueError('complete stationary-code native calibration required')
    deck=reference_deck(p);op=read(deck)
    if op['corner']not in('tt','ff','ss','sf','fs'):raise ValueError('declared prototype device corner required')
    with signals.open()as stream:
        reader=csv.DictReader(stream);rows=[(float(row['time']),float(row['v(pllout)']))for row in reader]
    if len(rows)!=a['samples']or not rows or rows[0][0]!=0 or abs(rows[-1][0]-260e-9)>1e-18 or any(not math.isfinite(t)or not math.isfinite(v)for t,v in rows)or any(x[0]>=y[0]for x,y in zip(rows,rows[1:])):raise ValueError('complete finite ordered native waveform required')
    edges=[(t+(.9-v)*(u-t)/(w-v))*1e9 for(t,v),(u,w)in zip(rows,rows[1:])if v<.9<=w]
    selected=[t for t in edges if start_ns<=t<=end_ns];result=statistics_from_edges(selected)
    paths=[provenance_path,signals,assessment,deck,Path(__file__).resolve(),Path(__file__).with_name('common_v3.py'),Path(__file__).with_name('selected_spice_device_conditions.py')];pins={str(path):sha(path)for path in paths};verify(pins)
    result.update(input_sha256=pins,window_ns=[start_ns,end_ns],edge_threshold_V=.9,coarse=a['coarse_code']['window_codes'][0],fine=a['dco_code']['window_codes'][0],device_conditions=op,
        scope='Finite-window noiseless native PLLOUT variation; includes deterministic startup drift and numerical variation.',thermal_and_flicker_noise_simulated=False,precision_jitter_qualified=False,jitter_limit_applied=False,target_preset_qualified=False,release_ready=False)
    save(output,result)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--provenance',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.provenance.resolve(),a.output.resolve())
