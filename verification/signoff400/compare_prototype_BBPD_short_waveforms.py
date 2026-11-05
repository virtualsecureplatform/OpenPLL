"""Compare complete short native captures of full/reduced coupled BBPD signal models."""
import argparse
from bisect import bisect_left
import json
from pathlib import Path
from common_v3 import save,sha,verify
from run_prototype_BBPD_short_probe import observe
from assess_prototype_native_waveform import crossings


def samples(text):
    result=[]
    for line in text.splitlines():
        f=line.split()
        if f and f[0].isdigit():result.append(tuple(map(float,f[1:])))
    return result


def interpolate(rows,times,t,column):
    index=bisect_left(times,t)
    if index<len(times) and times[index]==t:return rows[index][column]
    if not 0<index<len(rows):raise ValueError('query outside native capture')
    a,b=rows[index-1:index+1]
    return a[column]+(b[column]-a[column])*(t-a[0])/(b[0]-a[0])


def run(full,reduced,output):
    output.mkdir(parents=True,exist_ok=False);reports=[];data=[];pins={}
    for directory in (full,reduced):
        receipt=directory/'assessment.json';manifest=directory/'input_manifest.json';log=directory/'native.log'
        r=json.loads(receipt.read_text());verify(r['input_sha256']);verify(r['artifacts'])
        if r.get('native_short_horizon_completed') is not True:raise ValueError('complete native short capture required')
        observe(log.read_text(),r['stop_ns']);reports.append(r);data.append(samples(log.read_text()))
        pins.update({str(p):sha(p) for p in (receipt,manifest,log)})
    if reports[0]['stop_ns']!=reports[1]['stop_ns']:raise ValueError('capture horizons differ')
    a,b=data;at=[x[0] for x in a];bt=[x[0] for x in b];grid=sorted(set(at)|set(bt))
    if at[0]!=bt[0] or at[-1]!=bt[-1]:raise ValueError('native sampled domain mismatch')
    result={}
    for column,name in enumerate(('REF','DIV','RESET','DN','UP','DNQ','UPQ'),1):
        error=max(abs(interpolate(a,at,t,column)-interpolate(b,bt,t,column)) for t in grid)
        ae=crossings([(x[0],x[column]) for x in a],.9);be=crossings([(x[0],x[column]) for x in b],.9)
        same=all(len(x)==len(y) for x,y in zip(ae,be))
        deltas=[abs(x-y)*1e12 for xs,ys in zip(ae,be) for x,y in zip(xs,ys)] if same else []
        result[name]=dict(piecewise_linear_max_voltage_difference_v=error,threshold_crossing_counts_match=same,
            edge_counts=[[len(x) for x in edges] for edges in (ae,be)],maximum_paired_edge_difference_ps=max(deltas,default=None))
    pins.update({str(p):sha(p) for p in (Path(__file__).resolve(),Path(__file__).with_name('run_prototype_BBPD_short_probe.py'),Path(__file__).with_name('assess_prototype_native_waveform.py'))})
    detail=output/'comparison.json';save(detail,result);verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},stop_ns=reports[0]['stop_ns'],
        native_samples=[len(a),len(b)],native_sample_timestamps_identical=at==bt,
        maximum_observed_voltage_difference_v=max(x['piecewise_linear_max_voltage_difference_v'] for x in result.values()),
        all_signal_threshold_crossing_counts_match=all(x['threshold_crossing_counts_match'] for x in result.values()),
        full_90ns_native_correlation_complete=False,power_supply_current_noise_and_nonideal_rails_preserved=False,
        diagnostic=True,validated_for_prototype=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('full','reduced','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(a.full.resolve(),a.reduced.resolve(),a.output.resolve())
