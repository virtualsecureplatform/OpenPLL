"""Independently review off-grid native captures and report observed timing brackets."""
import argparse
import json
from pathlib import Path
from common_v3 import save,sha,verify,spec
from run_prototype_capture_refinement import table, OFFSETS
from run_prototype_capture_slow_data import OFFSETS as SLOW_OFFSETS
from run_prototype_clock_pulse_grid import LOADS


def transitions(rows,column,threshold):
    edges=[]
    for a,b in zip(rows,rows[1:]):
        if a[column]<threshold<=b[column] or a[column]>threshold>=b[column]:
            t=a[0]+(b[0]-a[0])*(threshold-a[column])/(b[column]-a[column])
            edges.append((t,1 if b[column]>a[column] else 0))
    return edges


def state(values):
    if max(values)<.36:return 0
    if min(values)>1.44:return 1
    return None


def point(directory):
    receipt=directory/'assessment.json';r=json.loads(receipt.read_text());verify(r['input_sha256']);verify(r['artifacts'])
    manifest=json.loads((directory/'input_manifest.json').read_text());cases=manifest['cases']
    offsets=OFFSETS if len(cases)==24 else SLOW_OFFSETS if len(cases)==30 else ()
    n=len(cases)
    expected={(kind,offset) for kind in ('data_rise','data_fall','async_release') for offset in offsets}
    if not offsets or {(c['kind'],c['offset_ps']) for c in cases}!=expected or r['cases']!=n:raise ValueError('exact supported capture grid required')
    data_ramp=manifest['input_full_ramp_ps'];clock_ramp=manifest.get('clock_full_ramp_ps',200)
    if data_ramp not in (200,1000) or clock_ramp!=200:raise ValueError('unsupported measured slew grid')
    if r['load_fF']!=LOADS[r['master'].split('__')[1]]:raise ValueError('master-specific native load mismatch')
    rows=table(directory/'waveform.dat',n);clock=transitions(rows,1,.9)
    rises=[t for t,d in clock if d]
    if len(rises)!=2 or any(abs(t-n*1e-9)>1e-12 for t,n in zip(rises,(10,20))):raise ValueError('clock capture mismatch')
    clock_lo=[t for t,d in transitions(rows,1,.36) if d];clock_hi=[t for t,d in transitions(rows,1,1.44) if d]
    if len(clock_lo)!=2 or len(clock_hi)!=2 or any(abs((hi-lo)*1e12-.6*clock_ramp)>1 for lo,hi in zip(clock_lo,clock_hi)):raise ValueError('clock slew mismatch')
    records=[]
    for i,case in enumerate(cases):
        q=2+i;change=2+n+i if case['kind']!='async_release' else 2+2*n+i
        direction=0 if case['kind']=='data_fall' else 1
        input_edges=[t for t,d in transitions(rows,change,.9) if d==direction]
        if len(input_edges)!=1 or abs((input_edges[0]-rises[1])*1e12-case['offset_ps'])>1:raise ValueError('changed input capture mismatch')
        low=[t for t,d in transitions(rows,change,.36) if d==direction]
        high=[t for t,d in transitions(rows,change,1.44) if d==direction]
        if len(low)!=1 or len(high)!=1 or abs(abs(high[0]-low[0])*1e12-.6*data_ramp)>1:raise ValueError('slew mismatch')
        pre=state([row[q] for row in rows if 17.5e-9<=row[0]<=18.5e-9])
        final=state([row[q] for row in rows if 27e-9<=row[0]<=30e-9])
        if pre!=case['pretest_expected']:raise ValueError('invalid native pretest state')
        events=[(t,d) for t,d in transitions(rows,q,.9) if t>=18.5e-9]
        changed=final==case['new_value'] and len(events)==1 and events[0][1]==case['new_value'] and events[0][0]>=rises[1]
        retained=final==pre and not events
        records.append(dict(kind=case['kind'],offset_ps=case['offset_ps'],final_value=final,
            output_crossings=[dict(clock_relative_ps=(t-rises[1])*1e12,direction=d) for t,d in events],
            clean_capture_of_new_value=changed,clean_retention_of_pretest_value=retained,
            unresolved_or_glitching=not(changed or retained)))
    brackets=[]
    for kind in ('data_rise','data_fall','async_release'):
        selected=[x for x in records if x['kind']==kind]
        before=sorted([x for x in selected if x['offset_ps']<0],key=lambda x:x['offset_ps'])
        after=sorted([x for x in selected if x['offset_ps']>0],key=lambda x:x['offset_ps'])
        good_before=[x['offset_ps'] for j,x in enumerate(before) if all(y['clean_capture_of_new_value'] for y in before[:j+1])]
        good_after=[x['offset_ps'] for j,x in enumerate(after) if all(y['clean_retention_of_pretest_value'] for y in after[j:])]
        brackets.append(dict(kind=kind,latest_sampled_clean_before_ps=max(good_before,default=None),
            earliest_sampled_clean_after_ps=min(good_after,default=None),continuum_bound_proved=False))
    return dict(corner=r['corner'],master=r['master'],load_fF=r['load_fF'],input_full_ramp_ps=data_ramp,clock_full_ramp_ps=clock_ramp,records=records,observed_brackets=brackets)


def run(campaign,output):
    receipt=campaign/'assessment.json';r=json.loads(receipt.read_text());verify(r['input_sha256']);verify(r['artifacts'])
    points=campaign/'points.json';rows=json.loads(points.read_text())
    expected={(c,m) for c in spec()['corners'] for m in LOADS}
    if len(rows)!=25 or {(x['corner'],x['master']) for x in rows}!=expected:raise ValueError('exact five-corner/master coverage required')
    output.mkdir(parents=True,exist_ok=False);pins={str(p):sha(p) for p in (receipt,points,Path(__file__).resolve(),Path(__file__).with_name('run_prototype_capture_refinement.py'),Path(__file__).with_name('run_prototype_capture_slow_data.py'))};results=[]
    for row in rows:
        directory=Path(row['directory']);rp=directory/'assessment.json'
        if sha(rp)!=row['assessment_sha256']:raise ValueError('native point receipt changed')
        results.append(point(directory));pins[str(rp)]=sha(rp)
    detail=output/'observations.json';save(detail,results);verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},
        exact_25_master_corner_grids_verified=True,reviewed_native_cases=sum(len(p['records']) for p in results),all_pretest_and_fixture_waveforms_valid=True,
        unresolved_or_glitching_cases=sum(x['unresolved_or_glitching'] for p in results for x in p['records']),
        observed_brackets_only=True,setup_hold_recovery_removal_qualified=False,load_and_slew_envelope_verified=False,
        numerical_uncertainty_bounded=False,validated_for_prototype=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--campaign',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();run(a.campaign.resolve(),a.output.resolve())
