"""Review broad-phase native detector behavior without forcing every sample to a binary decision."""
import argparse
import json
from pathlib import Path
import time
from common_v3 import save,sha,verify
from resources import identity
from run_prototype_BBPD_wide_phase import read_table
from review_prototype_BBPD_corrected_waveforms import measure
from review_prototype_BBPD_with_sync import sync_metrics


def classify(outputs):
    result=[]
    for start,stop in ((10.1,50.1),(50.1,90)):
        events=sorted((t,role) for role in ('DN','UP') for t in outputs[role]['detector_rising_edges_ns'] if start<=t<stop)
        label='NONE' if not events else events[0][1] if len(events)==1 else 'BOTH' if {r for t,r in events}=={'DN','UP'} and len(events)==2 else 'MULTIPLE'
        result.append(dict(reference_sample_ns=start,stop_ns=stop,decision=label,events=[dict(time_ns=t,role=r) for t,r in events]))
    return result


def run(sources,zero_review,output):
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    zr=zero_review/'assessment.json';z=json.loads(zr.read_text());verify(z['input_sha256']);verify(z['artifacts'])
    if z['complete_native_cases']!=15 or not z['first_sync_D_loads_and_wire_RCs_included']:raise ValueError('completed loaded zero-phase evidence required')
    zf=zero_review/'observations.json';zero=json.loads(zf.read_text());records=[];seen=set()
    for row in zero:
        if row['phase_ps']==0:records.append(dict(corner=row['corner'],phase_ps=0,outputs=row['detector_to_event_capture'],first_synchronizers=row['first_synchronizers'],reused_zero_phase=True,reference_decisions=classify(row['detector_to_event_capture'])))
    if len(records)!=5 or {r['corner'] for r in records}!={'tt','ff','ss','sf','fs'}:raise ValueError('five unique zero-phase points required')
    pins={str(p):sha(p) for p in (zr,zf,Path(__file__).resolve(),Path(__file__).with_name('run_prototype_BBPD_wide_phase.py'),Path(__file__).with_name('review_prototype_BBPD_with_sync.py'),Path(__file__).with_name('review_prototype_BBPD_corrected_waveforms.py'))}
    for source in sources:
        while not (source/'assessment.json').exists():
            owner=json.loads((source/'owner.json').read_text())
            if identity(owner['pid'])!=owner['birth']:raise ValueError('wide-phase native controller stopped without receipt')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('wide-phase review deadline')
            time.sleep(1)
        receipt=source/'assessment.json';r=json.loads(receipt.read_text());verify(r['input_sha256']);verify(r['artifacts'])
        corner=r['corner']
        if corner not in ('tt','ff','ss','sf','fs') or corner in seen:raise ValueError('unique supported wide-phase corner required')
        seen.add(corner)
        if not r['all_declared_native_waveforms_complete'] or not r['first_sync_input_loads_included'] or (r['aggressor_phase_ps'],r['sync_clock_phase_ps'],r['sync_Q_load_fF'])!=(325,345,20):raise ValueError('complete loaded wide-phase fixture required')
        manifest=source/'input_manifest.json';m=json.loads(manifest.read_text());verify(m['input_sha256'])
        if len(m['phase_ps'])!=3 or set(m['phase_ps'])!={10000,20000,30000}:raise ValueError('exact wide-phase grid required')
        declared=json.loads((source/'observations.json').read_text())
        if declared['failures']:raise ValueError('native failures cannot be concealed')
        by_phase={row['phase_ps']:row for row in declared['results']}
        for phase in m['phase_ps']:
            log=source/f'phase_{phase}ps/native.log'
            if r['artifacts'].get(str(log))!=sha(log):raise ValueError('unbound wide-phase waveform')
            rows=read_table(log.read_text());a=measure([row[:8] for row in rows],phase);sync=sync_metrics(rows)
            if any(by_phase[phase][k]!=v for k,v in a.items()) or by_phase[phase]['first_synchronizers']!=sync:raise ValueError('native broad-phase observations differ')
            records.append(dict(corner=corner,phase_ps=phase,outputs=a['outputs'],first_synchronizers=sync,reused_zero_phase=False,reference_decisions=classify(a['outputs'])))
            pins[str(log)]=sha(log)
        pins.update({str(p):sha(p) for p in (receipt,manifest,source/'observations.json')})
    if seen!={'tt','ff','ss','sf','fs'}:raise ValueError('all five broad-phase corners required')
    detail=output/'observations.json';save(detail,records);verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},native_phase_points=len(records),
        all_sync_captures_match=all(s['one_delayed_capture_per_source_toggle_observed'] for r in records for s in r['first_synchronizers'].values()),
        missing_or_multiple_detector_decisions_retained=True,native_full_phase_guard_verified=True,
        actual_divider_startup_waveforms_covered=False,numerical_and_model_uncertainty_included=False,
        diagnostic=True,native_interface_qualified=False,validated_for_prototype=False,release_ready=False))
    print('Reviewed wide-phase native points:',len(records))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--sources',type=Path,nargs='+',required=True);p.add_argument('--zero-review',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run([p.resolve() for p in a.sources],a.zero_review.resolve(),a.output.resolve())
