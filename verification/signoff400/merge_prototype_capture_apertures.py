"""Merge refined and coarse native aperture samples without discarding ambiguous captures."""
import argparse,json
from pathlib import Path
from common_v3 import save,sha,verify
from audit_prototype_final_campaign_coverage_v3 import merge_pins


def bracket(records):
    offsets=[r['offset_ps'] for r in records]
    if len(set(offsets))!=len(offsets):raise ValueError('duplicate capture offsets')
    before=sorted((r for r in records if r['offset_ps']<0),key=lambda r:r['offset_ps'])
    after=sorted((r for r in records if r['offset_ps']>0),key=lambda r:r['offset_ps'])
    clean_before=[r['offset_ps'] for i,r in enumerate(before) if all(x['clean_capture_of_new_value'] for x in before[:i+1])]
    clean_after=[r['offset_ps'] for i,r in enumerate(after) if all(x['clean_retention_of_pretest_value'] for x in after[i:])]
    if not clean_before or not clean_after:raise ValueError('coarse outer aperture brackets must remain covered')
    lo,hi=max(clean_before),min(clean_after)
    for r in records:
        if r['offset_ps']<=lo and not r['clean_capture_of_new_value']:raise ValueError('unsafe sample before bracket')
        if r['offset_ps']>=hi and not r['clean_retention_of_pretest_value']:raise ValueError('unsafe sample after bracket')
    return dict(latest_sampled_clean_before_ps=lo,earliest_sampled_clean_after_ps=hi,
        unresolved_or_glitching_samples=sum(r['unresolved_or_glitching'] for r in records),
        all_nonclean_samples_enclosed=True,continuum_bound_proved=False)


def add_pin(pins,path):
    name=str(path);digest=sha(path)
    if name in pins and pins[name]!=digest:raise ValueError('receipt/artifact identity changed: '+name)
    pins[name]=digest


def run(coarse,expanded,fast,refined,output):
    cr=coarse/'assessment.json';c=json.loads(cr.read_text());constraints=coarse/'constraints.json'
    if c['master_corner_constraint_sets']!=25 or not c['all_capture_apertures_bracketed']:raise ValueError('complete coarse constraints required')
    rr=refined/'assessment.json';r=json.loads(rr.read_text())
    if r['native_cases']!=3510 or r['operating_points']!=90:raise ValueError('complete two-master refinement required')
    paths=[cr,rr,constraints,Path(__file__).resolve()];pins={str(p):sha(p) for p in paths}
    merge_pins(pins,c);merge_pins(pins,r)
    original={}
    for campaign in (expanded,fast):
        receipt=campaign/'assessment.json';record=json.loads(receipt.read_text());merge_pins(pins,record);add_pin(pins,receipt)
        index=campaign/'points.json';add_pin(pins,index)
        for point in json.loads(index.read_text()):
            key=point['corner'],point['master'],point['data_ramp_ps'],point['clock_ramp_ps']
            if key in original:raise ValueError('duplicate coarse fixture')
            original[key]=Path(point['directory'])
    if len(original)!=225:raise ValueError('all coarse native fixture points required')
    tables=json.loads(constraints.read_text());by_key={(x['corner'],x['master']):x for x in tables}
    index=refined/'points.json';add_pin(pins,index);details=[];seen=set()
    for point in json.loads(index.read_text()):
        key=point['corner'],point['master'],point['data_ramp_ps'],point['clock_ramp_ps']
        if key in seen or key not in original:raise ValueError('duplicate or unknown refined fixture')
        seen.add(key);directory=Path(point['directory']);old=original[key]
        source_receipts=[];reviews=[]
        for where in (old,directory):
            native=where/'assessment.json';a=json.loads(native.read_text());merge_pins(pins,a);add_pin(pins,native)
            review=where.parent/(where.name+'_review');receipt=review/'assessment.json';b=json.loads(receipt.read_text());merge_pins(pins,b);add_pin(pins,receipt)
            if b['input_sha256'].get(str(native))!=sha(native) or not b['all_fixture_and_pretest_waveforms_valid']:raise ValueError('independent waveform review lineage differs')
            observed=review/'observations.json';add_pin(pins,observed);reviews.append(json.loads(observed.read_text()))
            source_receipts.append(a)
        if any((a['corner'],a['master'],a['input_full_ramp_ps'],a['clock_full_ramp_ps'],a['load_fF'])!=(key[0],'sky130_fd_sc_hs__'+key[1],key[2],key[3],point['load_fF']) for a in source_receipts):raise ValueError('load/slew/cell fixture differs')
        hashes=[{digest for name,digest in a['input_sha256'].items() if name.endswith('/cell.spice')} for a in source_receipts]
        if any(len(x)!=1 for x in hashes) or hashes[0]!=hashes[1]:raise ValueError('native cell model changed between coarse/refined points')
        constraint=by_key[key[0],'sky130_fd_sc_hs__'+key[1]]
        if constraint['native_cell_model_sha256']!=next(iter(hashes[0])):raise ValueError('constraint cell lineage differs')
        records=[x for review in reviews for x in review['records']]
        expected_offsets={-1500,-1000,-750,-500,-250,250,500,750,1000,1500,-200,-150,-100,-75,-50,-25,0,25,50,75,100,150,200}
        if len(records)!=69 or {x['kind'] for x in records}!={'data_rise','data_fall','async_release'} or any({x['offset_ps'] for x in records if x['kind']==kind}!=expected_offsets for kind in ('data_rise','data_fall','async_release')):
            raise ValueError('complete disjoint coarse and refined aperture samples required')
        result={kind:bracket([x for x in records if x['kind']==kind]) for kind in ('data_rise','data_fall','async_release')}
        d=(20,200,2000).index(key[2]);k=(20,200,400).index(key[3]);margin=constraint['engineering_margin_ps']
        for kind,before,after in (('data_rise','setup_rise_ps','hold_rise_ps'),('data_fall','setup_fall_ps','hold_fall_ps'),('async_release','recovery_rise_ps','removal_rise_ps')):
            constraint['tables'][before][d][k]=-result[kind]['latest_sampled_clean_before_ps']+margin
            constraint['tables'][after][d][k]=result[kind]['earliest_sampled_clean_after_ps']+margin
        details.append(dict(corner=key[0],master=key[1],input_full_ramp_ps=key[2],clock_full_ramp_ps=key[3],merged_native_cases=len(records),brackets=result,records=records))
    expected={(c,m,d,k) for c in ('tt','ff','ss','sf','fs') for m in ('dfrtp_1','dfstp_1') for d in (20,200,2000) for k in (20,200,400)}
    if seen!=expected:raise ValueError('complete refined two-master slew mesh required')
    verify(pins);output.mkdir(parents=True,exist_ok=False);target=output/'constraints.json';detail=output/'apertures.json';save(target,tables);save(detail,details)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in (target,detail)},
        native_capture_cases=10260,native_capture_grids=225,refined_native_capture_grids=90,master_corner_constraint_sets=25,
        all_capture_apertures_bracketed=True,all_ambiguous_samples_retained_and_enclosed=True,
        minimum_refined_grid_spacing_ps=25,engineering_margin_ps=c['engineering_margin_ps'],
        pulse_constraints_preserved=True,refined_numerical_boundary_holdouts_qualified=False,
        continuous_aperture_bound_proved=False,native_capture_constraints_qualified=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('coarse','expanded','fast','refined','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.coarse.resolve(),a.expanded.resolve(),a.fast.resolve(),a.refined.resolve(),a.output.resolve())
