"""Verify the exported load control releases only retained-output voltage boundaries."""
import argparse,collections,json
from pathlib import Path
from common_v3 import save,sha,verify
from compare_prototype_physical_primitive_graphs import Union
from compare_selected_dco_load_controls import canonical_deck
from audit_selected_dco_history_inputs import sources


def run(reference,target,old_plan,plan,model,output):
    if output.exists():raise FileExistsError(output)
    old,p=[json.loads(x.read_text()) for x in [old_plan,plan]];a,b=[json.loads((x/'manifest.json').read_text()) for x in [reference,target]]
    for x in [old,p,a,b]:verify(x['input_sha256'])
    if b['input_sha256'].get(str(plan))!=sha(plan) or a['input_sha256'].get(str(old_plan))!=sha(old_plan):raise ValueError('actual exported plans required')
    if any(x['input_sha256'].get(str(model))!=sha(model) for x in [old,p,a,b]):raise ValueError('same full physical model required')
    if old['selected_primitives']!=p['selected_primitives'] or a['observed_roles']!=b['observed_roles']:raise ValueError('nonlinear circuit or observations changed')
    union=Union()
    for line in model.open():
        f=line.split()
        if f and f[0][0].upper()=='R':union.join(f[1],f[2])
    protected={union.find(r['node']) for r in p['protected_retained_outputs']};x,y=sources(reference/'sources.spice'),sources(target/'sources.spice')
    expected={n for n in x if union.find(n) in protected};removed=set(x)-set(y)
    if not expected or removed!=expected or set(y)-set(x):raise ValueError('unexpected voltage boundary changes')
    if any(x[n][1]!=y[n][1] for n in y):raise ValueError('remaining source values changed')
    if any(union.find(n) in protected for n in y):raise ValueError('retained output R component remains prescribed')
    prescribed=set(p['prescribed_control_driver_input_nodes'])|{p['prescribed_reset_driver_input']}
    if not prescribed<=y.keys():raise ValueError('intended programming/reset input source removed')
    old_cards,new_cards=[collections.Counter((d/'devices.spice').read_text().splitlines()) for d in [reference,target]]
    if old_cards-new_cards:raise ValueError('original device/passive cards removed')
    added=list((new_cards-old_cards).elements())
    if not added or any(not line.split() or line.split()[0][0].upper() not in ['R','C'] for line in added):raise ValueError('only newly incident physical passive cards may be added')
    expected_cards=set(p['retained_passive_cards'])-set(old['retained_passive_cards'])
    if {line.split()[0] for line in added}!=expected_cards:raise ValueError('added passives differ from physical cut plan')
    physical_cards={}
    for line in model.open():
        fields=line.split()
        if fields and fields[0] in expected_cards:physical_cards[fields[0]]=line.strip()
    if any(physical_cards.get(line.split()[0])!=line.strip() for line in added):raise ValueError('added passive values differ from full physical model')
    if any(any(union.find(n) not in protected for n in line.split()[1:3]) for line in added if line.split()[0][0].upper()=='R'):raise ValueError('new wire resistor leaves protected output network')
    if canonical_deck((reference/'control.spice').read_text())!=canonical_deck((target/'control.spice').read_text()):raise ValueError('solver or transient protocol changed')
    files=[Path(__file__).resolve(),old_plan,plan,model,Path(__file__).with_name('compare_prototype_physical_primitive_graphs.py'),Path(__file__).with_name('compare_selected_dco_load_controls.py'),Path(__file__).with_name('audit_selected_dco_history_inputs.py')]+[d/n for d in [reference,target] for n in ['manifest.json','devices.spice','sources.spice','control.spice']]
    save(output,dict(input_sha256={str(x):sha(x) for x in files},all_original_device_and_passive_cards_retained=True,added_physical_resistors=sum(line.split()[0][0].upper()=='R' for line in added),added_physical_capacitors=sum(line.split()[0][0].upper()=='C' for line in added),removed_output_voltage_sources=sorted(removed),remaining_source_values_identical=True,all_retained_output_R_components_unclamped=True,intended_programming_and_reset_sources_retained=True,solver_and_observation_protocol_unchanged=True,DC_failure_cause_identified=False,release_ready=False));print('released output sources',len(removed),'added verified physical passive cards',len(added))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['reference','target','old-plan','plan','model','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['reference','target','old_plan','plan','model','output']))
