"""Verify a source-only time-zero exterior-state control, without node guesses."""
import argparse,json
from pathlib import Path
from common_v3 import save,sha,verify
from audit_selected_dco_history_inputs import sources
from check_selected_boundary_waveforms import bind
from compare_selected_dco_load_controls import canonical_deck


def run(reference,target,plan,snapshot,output):
    if output.exists():raise FileExistsError(output)
    p=json.loads(plan.read_text());s=json.loads(snapshot.read_text())
    verify(p['input_sha256']);verify(s['artifacts']);verify({k:v for k,v in s['input_sha256'].items() if not k.endswith('/profile.raw')})
    vectors=[Path(k) for k in s['artifacts'] if k.endswith('/initial_voltage_vector.json')]
    if len(vectors)!=1:raise ValueError('unique verified vector required')
    initial=json.loads(vectors[0].read_text())
    if initial['time_s']!=0:raise ValueError('time-zero vector required')
    a,b=[json.loads((d/'manifest.json').read_text()) for d in [reference,target]]
    for m in [a,b]:
        verify(m['input_sha256'])
        if m['input_sha256'].get(str(plan))!=sha(plan) or m['input_sha256'].get(str(snapshot))!=sha(snapshot):raise ValueError('same plan and full-native snapshot required')
    if b['input_sha256'].get(str(vectors[0]))!=sha(vectors[0]):raise ValueError('executed deck must pin initial vector')
    for k in ['controls','operating_point','observed_roles']:
        if a[k]!=b[k]:raise ValueError('programming, corner or observations changed')
    if (reference/'devices.spice').read_bytes()!=(target/'devices.spice').read_bytes():raise ValueError('physical cards changed')
    if canonical_deck((reference/'control.spice').read_text())!=canonical_deck((target/'control.spice').read_text()):raise ValueError('solver, node guesses or transient protocol changed')
    x,y=sources(reference/'sources.spice'),sources(target/'sources.spice')
    if x.keys()!=y.keys():raise ValueError('voltage-source boundary changed')
    controls=set(p['prescribed_control_driver_input_nodes'])|{p['prescribed_reset_driver_input']}
    boundaries=set(p['required_non_supply_boundary_voltage_nodes']);quiet=boundaries-controls
    bound=bind(quiet,initial['variable_names'])
    if not bound['all_bound']:raise ValueError('all quiet nodes must bind to full initial state')
    for n in y:
        if n in quiet:
            if float(y[n][1])!=initial['values'][bound['bindings'][n]['index']]:raise ValueError('exterior source differs from recorded initial value: '+n)
        elif x[n][1]!=y[n][1]:raise ValueError('programming, reset or supply changed: '+n)
    files=[Path(__file__).resolve(),plan,snapshot,vectors[0],Path(__file__).with_name('audit_selected_dco_history_inputs.py'),Path(__file__).with_name('check_selected_boundary_waveforms.py'),Path(__file__).with_name('compare_selected_dco_load_controls.py')]+[d/n for d in [reference,target] for n in ['manifest.json','sources.spice','devices.spice','control.spice']]
    save(output,dict(input_sha256={str(f):sha(f) for f in files},quiet_exterior_nodes_verified=len(quiet),changed_exterior_nodes=sum(x[n][1]!=y[n][1] for n in quiet),source_boundaries_identical=True,all_physical_cards_identical=True,programming_reset_and_supplies_identical=True,solver_and_observation_protocol_identical=True,node_guesses_added=False,full_native_initial_state_preserved_at_exterior=True,exterior_switching_qualified=False,DC_failure_cause_identified=False,release_ready=False))
    print('verified time-zero exterior nodes',len(quiet))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['reference','target','plan','snapshot','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['reference','target','plan','snapshot','output']))
