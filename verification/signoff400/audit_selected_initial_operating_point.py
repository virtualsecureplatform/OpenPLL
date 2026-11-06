"""Audit the one-nanosecond, fully coherent exterior-state DC control."""
import argparse,json
from pathlib import Path
from common_v3 import save,sha,verify
from audit_selected_dco_history_inputs import sources
from check_selected_boundary_waveforms import bind
from compare_selected_dco_load_controls import canonical_deck


def run(reference,target,plan,snapshot,output):
    if output.exists():raise FileExistsError(output)
    p=json.loads(plan.read_text());s=json.loads(snapshot.read_text())
    verify(p['input_sha256']);verify(s['artifacts'])
    vectors=[Path(k) for k in s['artifacts'] if k.endswith('/initial_voltage_vector.json')]
    if len(vectors)!=1:raise ValueError('unique verified vector required')
    initial=json.loads(vectors[0].read_text())
    if initial['time_s']!=0:raise ValueError('time-zero vector required')
    a,b=[json.loads((d/'manifest.json').read_text()) for d in [reference,target]]
    for m in [a,b]:
        verify(m['input_sha256'])
        if m['input_sha256'].get(str(plan))!=sha(plan) or m['input_sha256'].get(str(snapshot))!=sha(snapshot):raise ValueError('same partition and recorded state required')
    if b['input_sha256'].get(str(vectors[0]))!=sha(vectors[0]):raise ValueError('executed input must pin initial vector')
    if a['observed_roles']!=b['observed_roles'] or a['operating_point']!=b['operating_point']:raise ValueError('observations or PVT changed')
    if (reference/'devices.spice').read_bytes()!=(target/'devices.spice').read_bytes():raise ValueError('physical cards changed')
    deck=(target/'control.spice').read_text()
    if deck.count('.tran 10p 1n 0 10p')!=1:raise ValueError('exact short DC observation required')
    if canonical_deck(deck.replace('.tran 10p 1n 0 10p','.tran 10p 60n 0 10p'))!=canonical_deck((reference/'control.spice').read_text()):raise ValueError('other solver/protocol changes')
    x,y=sources(reference/'sources.spice'),sources(target/'sources.spice')
    if x.keys()!=y.keys():raise ValueError('source boundaries changed')
    nodes=set(p['required_non_supply_boundary_voltage_nodes']);bound=bind(nodes,initial['variable_names'])
    if not bound['all_bound']:raise ValueError('complete source binding required')
    for n in y:
        if n in nodes:
            if float(y[n][1])!=initial['values'][bound['bindings'][n]['index']]:raise ValueError('source differs from original recorded initial state: '+n)
        elif x[n][1]!=y[n][1]:raise ValueError('supply source changed')
    changes=[]
    for n in p['prescribed_control_driver_input_nodes']:
        actual=float(y[n][1]);static=float(x[n][1])
        if abs(actual-static)>.1:changes.append(dict(node=n,recorded_initial_voltage=actual,static_target_voltage=static))
    files=[Path(__file__).resolve(),Path(__file__).with_name('audit_selected_dco_history_inputs.py'),Path(__file__).with_name('check_selected_boundary_waveforms.py'),Path(__file__).with_name('compare_selected_dco_load_controls.py'),plan,snapshot,vectors[0]]+[d/n for d in [reference,target] for n in ['manifest.json','devices.spice','sources.spice','control.spice']]
    save(output,dict(input_sha256={str(f):sha(f) for f in files},recorded_initial_exterior_sources_verified=len(nodes),programming_initial_state_differences_from_static_target=changes,all_physical_cards_identical=True,source_boundaries_and_supplies_identical=True,only_observation_horizon_changed=True,node_guesses_added=False,reset_release_observed=False,frequency_calibration=False,DC_failure_cause_identified=False,release_ready=False))
    print('verified coherent exterior sources',len(nodes),'different static programming inputs',len(changes))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['reference','target','plan','snapshot','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['reference','target','plan','snapshot','output']))
