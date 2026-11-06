"""Verify the driven-input control adds only declared exterior source boundaries."""
import argparse,json
from pathlib import Path
from common_v3 import save,sha,verify
from audit_selected_dco_history_inputs import sources
from compare_selected_dco_load_controls import canonical_deck
from compare_prototype_physical_primitive_graphs import Union


def run(reference,target,old_plan,plan,output):
    if output.exists():raise FileExistsError(output)
    old,p=[json.loads(x.read_text()) for x in [old_plan,plan]];a,b=[json.loads((d/'manifest.json').read_text()) for d in [reference,target]]
    for v in [old,p,a,b]:verify(v['input_sha256'])
    if p['input_sha256'].get(str(old_plan))!=sha(old_plan) or a['input_sha256'].get(str(old_plan))!=sha(old_plan) or b['input_sha256'].get(str(plan))!=sha(plan):raise ValueError('actual old/new plan lineage required')
    if old['selected_primitives']!=p['selected_primitives'] or old['retained_passive_cards']!=p['retained_passive_cards']:raise ValueError('nonlinear/passive card set changed')
    if (reference/'devices.spice').read_bytes()!=(target/'devices.spice').read_bytes():raise ValueError('exported physical cards changed')
    for k in ['operating_point','observed_roles']:
        if a[k]!=b[k]:raise ValueError('operating point or observations changed')
    decks=[(d/'control.spice').read_text() for d in [reference,target]]
    if any(t.count('.tran 10p 1n 0 10p')!=1 for t in decks) or canonical_deck(decks[0].replace('.tran 10p 1n 0 10p','.tran 10p 60n 0 10p'))!=canonical_deck(decks[1].replace('.tran 10p 1n 0 10p','.tran 10p 60n 0 10p')):raise ValueError('solver or protocol changed')
    x,y=sources(reference/'sources.spice'),sources(target/'sources.spice');expected={r['node'] for r in p['added_explicit_input_source_cuts']}
    if x.keys()-y.keys() or y.keys()-x.keys()!=expected or any(x[n][1]!=y[n][1] for n in x):raise ValueError('unexpected source changes')
    model=next(Path(k) for k in p['input_sha256'] if Path(k).name=='model.spice');u=Union()
    for line in model.open():
        f=line.split()
        if f and f[0][0].upper()=='R':u.join(f[1],f[2])
    protected={u.find(r['node']) for r in p['protected_retained_outputs']}
    if any(u.find(n) in protected for n in y):raise ValueError('retained output is voltage-prescribed')
    files=[Path(__file__).resolve(),old_plan,plan,model,Path(__file__).with_name('audit_selected_dco_history_inputs.py'),Path(__file__).with_name('compare_selected_dco_load_controls.py'),Path(__file__).with_name('compare_prototype_physical_primitive_graphs.py')]+[d/n for d in [reference,target] for n in ['manifest.json','devices.spice','sources.spice','control.spice']]
    save(output,dict(input_sha256={str(f):sha(f) for f in files},added_explicit_input_sources=sorted(expected),all_old_source_values_identical=True,all_physical_cards_identical=True,solver_and_observation_protocol_identical=True,all_retained_output_R_components_unclamped=True,DC_failure_cause_identified=False,release_ready=False));print('verified added input sources',len(expected))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['reference','target','old-plan','plan','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['reference','target','old_plan','plan','output']))
