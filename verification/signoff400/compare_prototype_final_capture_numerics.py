"""Compare the final loaded FF/SS numerical holdouts against identical physical fixtures."""
import argparse
import hashlib
import json
from pathlib import Path
import re
from common_v3 import save, sha, verify
from audit_prototype_final_campaign_coverage_v3 import merge_pins, MASTERS


def fixture_signature(text,cell):
    includes=re.findall(r'^\.include "([^"]+)"$',text,re.M)
    if len(includes)!=1 or Path(includes[0]).resolve()!=Path(cell).resolve():
        raise ValueError('native deck must include the pinned cell model')
    text=re.sub(r'^\.include "[^"]+"$', '.include VERIFIED_IDENTICAL_CELL',text,flags=re.M)
    text=re.sub(r'^\.option klu reltol=\S+ abstol=\S+ num_threads=1$',
                '.option klu VERIFIED_NUMERICAL_PROFILE num_threads=1',text,flags=re.M)
    text=re.sub(r'^tran [0-9.]+p 30n 0 [0-9.]+p$',
                'tran VERIFIED_STEP 30n 0 VERIFIED_STEP',text,flags=re.M)
    waves=re.findall(r'^wrdata (\S+) (.+)$',text,re.M)
    if len(waves)!=1:raise ValueError('one explicit native waveform output required')
    text=re.sub(r'^wrdata \S+ (.+)$',r'wrdata VERIFIED_OUTPUT \1',text,flags=re.M)
    return hashlib.sha256(text.encode()).hexdigest()


def compare_cases(a,b):
    if a.keys()!=b.keys():raise ValueError('capture phase grids differ')
    differences=[];displacements=[]
    for key,x in sorted(a.items()):
        y=b[key]
        fields=('final_value','clean_capture_of_new_value','clean_retention_of_pretest_value','unresolved_or_glitching')
        ae,be=x['output_crossings'],y['output_crossings']
        if any(x[f]!=y[f] for f in fields) or [e['direction'] for e in ae]!=[e['direction'] for e in be]:
            differences.append(dict(case=list(key),baseline=x,holdout=y))
        else:
            displacements.extend(abs(e['clock_relative_ps']-f['clock_relative_ps']) for e,f in zip(ae,be))
    return differences,displacements


def read_point(directory,review,pins):
    nr=directory/'assessment.json';rr=review/'assessment.json'
    n,r=[json.loads(p.read_text()) for p in (nr,rr)]
    merge_pins(pins,n);merge_pins(pins,r)
    if r['input_sha256'].get(str(nr))!=sha(nr):raise ValueError('independent review/native point mismatch')
    if r['reviewed_native_cases']!=30 or not r['all_fixture_and_pretest_waveforms_valid']:
        raise ValueError('complete independent native capture review required')
    detail=review/'observations.json';data=json.loads(detail.read_text())
    decks=[Path(p) for p in n['input_sha256'] if p.endswith('/refinement.cir')]
    cells=[p for p in n['input_sha256'] if p.endswith('/cell.spice')]
    if len(decks)!=1 or len(cells)!=1:raise ValueError('unique native deck and cell model required')
    text=decks[0].read_text()
    options=re.findall(r'\.option klu reltol=(\S+) abstol=(\S+) num_threads=1',text)
    step=re.findall(r'tran ([0-9.]+)p 30n 0 ([0-9.]+)p',text)
    if len(options)!=1 or len(step)!=1 or step[0][0]!=step[0][1]:raise ValueError('explicit numerical profile required')
    profile=dict(maximum_step_ps=float(step[0][1]),reltol=float(options[0][0]),abstol=float(options[0][1]),
                 cell_model_sha256=n['input_sha256'][cells[0]],
                 physical_fixture_sha256=fixture_signature(text,cells[0]))
    key=(n['corner'],n['master'].removeprefix('sky130_fd_sc_hs__'),n['input_full_ramp_ps'],n['clock_full_ramp_ps'])
    cases={(c['kind'],c['offset_ps']):c for c in data['records']}
    if len(cases)!=30 or data['load_fF']!=n['load_fF']:raise ValueError('capture case or load mismatch')
    for p in (nr,rr,detail):
        digest=sha(p)
        if str(p) in pins and pins[str(p)]!=digest:raise ValueError('native/review receipt changed')
        pins[str(p)]=digest
    return key,n['load_fF'],data,cases,profile


def run(campaign,fast,expanded,output):
    receipt=campaign/'assessment.json';r=json.loads(receipt.read_text())
    points=campaign/'points.json';rows=json.loads(points.read_text())
    pins={str(p):sha(p) for p in (receipt,points,Path(__file__).resolve(),
          Path(__file__).with_name('audit_prototype_final_campaign_coverage_v3.py'))};merge_pins(pins,r)
    expected={(c,m,d,k) for c in ('ff','ss') for m in MASTERS for d,k in ((20,20),(2000,400))}
    seen=set();results=[];all_differences=[];all_displacements=[]
    for row in rows:
        where=Path(row['directory']);review=Path(row['review_directory'])
        if sha(where/'assessment.json')!=row['assessment_sha256'] or sha(review/'assessment.json')!=row['review_sha256']:
            raise ValueError('holdout native/review lineage changed')
        key,load,b,bc,bp=read_point(where,review,pins)
        if key in seen:raise ValueError('duplicate numerical holdout point')
        seen.add(key);c,m,d,k=key;baseline=(fast if (d,k)==(20,20) else expanded)/f'{c}_{m}_d{d}_c{k}'
        ak,al,a,ac,ap=read_point(baseline,baseline.parent/(baseline.name+'_review'),pins)
        if ak!=key or al!=load:raise ValueError('same physical native load and slew fixture required')
        if (ap['cell_model_sha256']!=bp['cell_model_sha256'] or ap['physical_fixture_sha256']!=bp['physical_fixture_sha256']
                or not all(0<bp[f]<ap[f] for f in ('maximum_step_ps','reltol','abstol'))):
            raise ValueError('identical cell model and strictly tighter numerical settings required')
        differences,displacements=compare_cases(ac,bc);all_displacements.extend(displacements)
        all_differences.extend(dict(point=list(key),**v) for v in differences)
        brackets=[]
        for kind in ('data_rise','data_fall','async_release'):
            left=next(x for x in a['observed_brackets'] if x['kind']==kind)
            right=next(x for x in b['observed_brackets'] if x['kind']==kind)
            before=[x['latest_sampled_clean_before_ps'] for x in (left,right)]
            after=[x['earliest_sampled_clean_after_ps'] for x in (left,right)]
            brackets.append(dict(kind=kind,latest_clean_before_in_both_profiles_ps=None if None in before else min(before),
                 earliest_clean_after_in_both_profiles_ps=None if None in after else max(after)))
        results.append(dict(corner=c,master=m,data_ramp_ps=d,clock_ramp_ps=k,load_fF=load,
             baseline_profile=ap,holdout_profile=bp,changed_outcome_cases=len(differences),
             maximum_matched_edge_displacement_ps=max(displacements,default=0),shared_observed_brackets=brackets))
    if seen!=expected:raise ValueError('complete FF/SS fast/slow five-master numerical holdout stencil required')
    verify(pins);output.mkdir(parents=True,exist_ok=False);detail=output/'comparison.json'
    save(detail,dict(points=results,differences=all_differences))
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},
         compared_native_case_pairs=600,compared_operating_points=20,
         all_paired_cell_models_identical=True,all_holdout_numerical_profiles_strictly_tighter=True,
         changed_outcome_cases=len(all_differences),all_sampled_outcomes_and_crossing_counts_match=not all_differences,
         matched_output_edges=len(all_displacements),maximum_paired_edge_displacement_ps=max(all_displacements,default=0),
         scope='FF/SS, five final FF masters, expanded loads, fastest and slowest measured slew endpoints',
         universal_numerical_error_bound_claimed=False,setup_hold_recovery_removal_qualified=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('campaign','fast','expanded','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.campaign.resolve(),a.fast.resolve(),a.expanded.resolve(),a.output.resolve())
