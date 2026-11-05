#!/usr/bin/env python3
"""Inventory capacitor support proximity to retained native R representatives.

Keep the original full-geometry C trace. Match original conductor names to the
native R provenance and inspect each unique support box using a per-conductor
spatial index. Report exact containment or minimum padding to a retained R
representative, never reinterpret an edge support as a capacitor point. This
prepares placement work; it creates no runtime netlist or physical qualification.
"""
from collections import defaultdict,Counter
from datetime import datetime,timezone
from pathlib import Path
import hashlib,json,math,os,shlex,signal,time
import numpy as np
from scipy.spatial import cKDTree
from audit_active_dco_rc_capacitance import parse,terminals
from run_dco_qualification import ROOT,sha,save


def main():
    base=ROOT/'build/timing400/release_001';meta=base/'DCO_R_node_provenance_inspection_002/node_metadata.json'
    trace_dir=base/'DCO_resistance_enabled_C_context_001/nom_trace';trace=trace_dir/'contributions.log'
    r_dir=base/'DCO_R_node_trace_controls_002/trace'
    top='IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160'
    owner_path=base/'candidate_layout_checks_001/owner.json';deadline=json.loads(owner_path.read_text())['deadline_uptime']
    left=deadline-time.clock_gettime(time.CLOCK_BOOTTIME);assert left>0;signal.alarm(max(1,math.floor(left)))
    out=base/'DCO_C_R_support_inventory_001';out.mkdir(exist_ok=False)
    save(out/'owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),original_owner=str(owner_path),
        deadline_uptime=deadline,total_budget_restarted=False,automatic_identical_retry=False))
    for directory in [r_dir,trace_dir]:
        with (directory/(top+('.res.ext' if directory==r_dir else '.ext'))).open() as stream:
            scale=next(l.split() for l in stream if l.startswith('scale '));assert scale[3]=='500000'
    raw=parse(r_dir/(top+'.rcx.spice'));active=set(raw['ports'])|{n for a,b,r in raw['R'] for n in [a,b]}
    for row in raw['X'].values():active.update(row[:terminals(row)])
    assert len(active)==78613
    points=defaultdict(lambda:defaultdict(set))
    for row in json.loads(meta.read_text()):
        if row['name'] in active:points[row['original_conductor']][tuple(row['point_internal'])].add(row['name'])
    indexes={}
    for net,locations in points.items():
        coordinates=np.asarray(sorted(locations),dtype=np.float64)
        indexes[net]=(cKDTree(coordinates),coordinates,locations)
    ids={};digest=hashlib.sha256();begins=ends=0
    save(out/'status.json',dict(state='reading_native_C_node_ids',release_qualified=False))
    with trace.open('rb') as stream:
        for line in stream:
            digest.update(line)
            if line.startswith(b'OPENPLL_ID '):
                f=shlex.split(line.decode());assert len(f)==4 and f[1] not in ids
                ids[f[1]]=f[2]
            elif line.startswith(b'OPENPLL_BEGIN '):begins+=1
            elif line.strip()==b'OPENPLL_END':ends+=1
    assert begins==ends==1
    # Confirm source trace provenance before relying on any spatial observation.
    source_receipt=json.loads((trace_dir.parent/'assessment.json').read_text())
    assert digest.hexdigest()==source_receipt['artifacts'][str(trace)]
    cache={};stats=Counter();by_reason=defaultdict(Counter);missing=Counter();maximum=0.;events=0
    support_file=(out/'support_boxes.jsonl').open('x')
    def inspect(net,box):
        nonlocal maximum
        key=(net,*box)
        if key in cache:return cache[key]
        l,b,r,t=box;assert l<=r and b<=t
        if net not in indexes:
            answer=dict(original_conductor=net,box_internal=box,retained_R_conductor_found=False)
        else:
            tree,xy,names=indexes[net];center=np.asarray([(l+r)/2,(b+t)/2]);half=max(r-l,t-b)/2
            padding=0.;indices=[]
            for attempt in range(32):
                candidates=tree.query_ball_point(center,half+padding+1e-8,p=np.inf)
                if candidates:
                    subset=xy[candidates]
                    distances=np.maximum.reduce([l-subset[:,0],subset[:,0]-r,b-subset[:,1],subset[:,1]-t,np.zeros(len(candidates))])
                    keep=np.flatnonzero(distances<=padding+1e-8)
                    if len(keep):
                        distance=float(np.min(distances[keep]));indices=[candidates[i] for i in keep if abs(float(distances[i])-distance)<1e-8];break
                padding=1. if padding==0 else 2*padding
            assert indices,(net,box)
            representatives=[]
            for index in indices[:3]:
                point=tuple(int(v) for v in xy[index]);representatives.append(dict(point_internal=list(point),nodes=sorted(names[point])))
            maximum=max(maximum,distance)
            answer=dict(original_conductor=net,box_internal=box,retained_R_conductor_found=True,
                nearest_representative_padding_internal=distance,nearest_representative_padding_nm=distance*5,
                exact_representative_point_in_support=distance==0,nearest_coordinate_count=len(indices),example_representatives=representatives)
        cache[key]=answer;support_file.write(json.dumps(answer)+'\n');return answer
    try:
        with trace.open() as stream:
            for line in stream:
                if line.startswith('OPENPLL_G '):
                    f=line.split();assert len(f) in [5,9];reason=f[3]
                    endpoints=[(ids[f[1]],list(map(int,f[5:9])))] if f[4]=='box' else []
                elif line.startswith('OPENPLL_P '):
                    f=line.split();assert len(f)==14 and f[5]=='boxes';reason=f[4]
                    endpoints=[(ids[f[1]],list(map(int,f[6:10]))),(ids[f[2]],list(map(int,f[10:14])))]
                else:continue
                events+=1
                if not endpoints:stats['unlocated_events']+=1
                for net,box in endpoints:
                    answer=inspect(net,box);by_reason[reason]['endpoints']+=1;stats['endpoints']+=1
                    if not answer['retained_R_conductor_found']:
                        stats['missing_original_conductor']+=1;by_reason[reason]['missing_original_conductor']+=1;missing[net]+=1
                    else:
                        state='exact_R_representative_in_support' if answer['exact_representative_point_in_support'] else 'support_requires_nonzero_representative_padding'
                        stats[state]+=1;by_reason[reason][state]+=1
                if events%1000000==0:
                    assert time.clock_gettime(time.CLOCK_BOOTTIME)<deadline
                    save(out/'status.json',dict(state='inventorying_C_R_support_boxes',events=events,unique_support_boxes=len(cache),release_qualified=False))
    finally:support_file.close()
    assert events==8297230
    save(out/'summary.json',dict(events=events,unique_support_boxes=len(cache),endpoint_classification=dict(stats),
        by_reason={k:dict(v) for k,v in by_reason.items()},missing_conductor_names=dict(missing),
        maximum_nearest_representative_padding_nm=maximum*5))
    paths=[Path(__file__).resolve(),meta,trace,trace_dir.parent/'assessment.json',r_dir/(top+'.rcx.spice'),owner_path,
        base/'DCO_R_node_trace_controls_002/assessment.json',Path(__file__).with_name('audit_active_dco_rc_capacitance.py')]
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in paths},artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file() and p.name not in ['owner.json','status.json']},
        native_C_trace_events=events,native_geometry_modified=False,capacitor_or_resistor_values_modified=False,
        C_support_proximity_is_not_a_placement_or_error_bound=True,native_analog_jobs_started=0,
        distributed_C_and_junction_allocation_or_transient_error_qualified=False,release_qualified=False,adopted=False,scope=__doc__))
    save(out/'status.json',dict(state='C_R_support_inventory_terminal',events=events,unique_support_boxes=len(cache),release_qualified=False))
    print('C/R support inventory completed:',events,'events;',dict(stats),'missing original conductors',dict(missing),'; placement remains unqualified.')


if __name__=='__main__':main()
