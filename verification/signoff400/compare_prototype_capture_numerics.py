"""Compare independent waveform reviews at two native numerical profiles."""
import argparse,json,re
from pathlib import Path
from common_v3 import save,sha,verify


def load(directory):
    receipt=directory/'assessment.json';r=json.loads(receipt.read_text());verify(r['input_sha256']);verify(r['artifacts'])
    if r.get('reviewed_native_cases')!=600 or not r['all_pretest_and_fixture_waveforms_valid']:raise ValueError('independent complete 600-case waveform review required')
    report=directory/'observations.json';rows=json.loads(report.read_text())
    keyed={}
    for point in rows:
        key=(point['corner'],point['master'])
        if key in keyed:raise ValueError('duplicate master/corner review')
        cases={(x['kind'],x['offset_ps']):x for x in point['records']}
        if len(cases)!=24:raise ValueError('duplicate or missing capture cases')
        keyed[key]=(point,cases)
    return receipt,report,keyed


def numerical_profiles(review):
    r=json.loads((review/'assessment.json').read_text());profiles={}
    for path,digest in r['input_sha256'].items():
        if not path.endswith('/assessment.json'):continue
        point=json.loads(Path(path).read_text())
        if point.get('cases')!=24:continue
        decks=[Path(p) for p in point['input_sha256'] if p.endswith('/refinement.cir')]
        cells=[(p,h) for p,h in point['input_sha256'].items() if p.endswith('/cell.spice')]
        if len(decks)!=1 or len(cells)!=1 or sha(decks[0])!=point['input_sha256'][str(decks[0])]:raise ValueError('pinned native deck and cell model required')
        text=decks[0].read_text()
        options=re.findall(r'\.option klu reltol=(\S+) abstol=(\S+) num_threads=1',text)
        step=re.findall(r'tran ([0-9.]+)p 30n 0 ([0-9.]+)p',text)
        if len(options)!=1 or len(step)!=1 or step[0][0]!=step[0][1]:raise ValueError('explicit native numerical settings required')
        key=(point['corner'],point['master'])
        if key in profiles:raise ValueError('duplicate native numerical profile')
        profiles[key]=dict(maximum_step_ps=float(step[0][1]),reltol=float(options[0][0]),abstol=float(options[0][1]),cell_model_sha256=cells[0][1])
    if len(profiles)!=25:raise ValueError('all 25 numerical profiles required')
    return profiles


def run(baseline,holdout,output):
    ar,af,a=load(baseline);br,bf,b=load(holdout)
    if a.keys()!=b.keys() or len(a)!=25:raise ValueError('matching 25 master/corner grids required')
    ap,bp=numerical_profiles(baseline),numerical_profiles(holdout)
    if ap.keys()!=a.keys() or bp.keys()!=a.keys():raise ValueError('native numerical profile coverage mismatch')
    for key in a:
        if ap[key]['cell_model_sha256']!=bp[key]['cell_model_sha256'] or not all(0<bp[key][k]<ap[key][k] for k in ('maximum_step_ps','reltol','abstol')):raise ValueError('matched device model and strictly tighter holdout profile required')
    output.mkdir(parents=True,exist_ok=False);results=[];differences=[]
    for key,(pa,ca) in sorted(a.items()):
        pb,cb=b[key]
        if pa['load_fF']!=pb['load_fF'] or ca.keys()!=cb.keys():raise ValueError('matched physical fixtures required')
        delta=[];changed=[]
        for case,x in sorted(ca.items()):
            y=cb[case]
            comparable=(x['final_value'],x['clean_capture_of_new_value'],x['clean_retention_of_pretest_value'],x['unresolved_or_glitching'])==(y['final_value'],y['clean_capture_of_new_value'],y['clean_retention_of_pretest_value'],y['unresolved_or_glitching'])
            ae,be=x['output_crossings'],y['output_crossings']
            if not comparable or len(ae)!=len(be) or [e['direction'] for e in ae]!=[e['direction'] for e in be]:
                changed.append(list(case));differences.append(dict(corner=key[0],master=key[1],case=list(case),baseline=x,holdout=y))
            else:delta.extend(abs(e['clock_relative_ps']-f['clock_relative_ps']) for e,f in zip(ae,be))
        brackets=[]
        for kind in ('data_rise','data_fall','async_release'):
            left=next(x for x in pa['observed_brackets'] if x['kind']==kind);right=next(x for x in pb['observed_brackets'] if x['kind']==kind)
            before=[p['latest_sampled_clean_before_ps'] for p in (left,right)];after=[p['earliest_sampled_clean_after_ps'] for p in (left,right)]
            brackets.append(dict(kind=kind,latest_clean_before_in_both_profiles_ps=None if None in before else min(before),
                earliest_clean_after_in_both_profiles_ps=None if None in after else max(after)))
        results.append(dict(corner=key[0],master=key[1],changed_outcome_cases=changed,
            maximum_matched_output_edge_displacement_ps=max(delta,default=0),observed_brackets=brackets))
    detail=output/'comparison.json';save(detail,dict(points=results,differences=differences))
    pins={str(p):sha(p) for p in (ar,af,br,bf,Path(__file__).resolve())};verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},compared_cases=600,all_holdout_numerical_profiles_strictly_tighter=True,all_paired_cell_models_identical=True,
        changed_outcome_cases=len(differences),all_sampled_capture_outcomes_and_crossing_counts_match=not differences,
        maximum_paired_output_edge_displacement_ps=max(x['maximum_matched_output_edge_displacement_ps'] for x in results),
        complete_load_and_slew_envelope_covered=False,universal_numerical_error_bound_claimed=False,
        setup_hold_recovery_removal_qualified=False,validated_for_prototype=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('baseline','holdout','output'):p.add_argument('--'+n,required=True,type=Path)
    a=p.parse_args();run(a.baseline.resolve(),a.holdout.resolve(),a.output.resolve())
