"""Allow only declared static programming changes at actual physical driver inputs."""
import argparse,json
from pathlib import Path
from common_v3 import save,sha,verify
from audit_selected_dco_history_inputs import sources
from compare_selected_dco_load_controls import canonical_deck
from run_selected_dco_real_driver_control_v3 import programming_sources


def run(reference,target,inventory,output):
    if output.exists():raise FileExistsError(output)
    a,b=[json.loads((p/'manifest.json').read_text()) for p in [reference,target]];i=json.loads(inventory.read_text())
    for value in [a,b,i]:verify(value['input_sha256'])
    for key in ['operating_point','observed_roles','quiet_exterior_snapshot_operating_point','exterior_condition']:
        if a[key]!=b[key]:raise ValueError('operating point, observations or exterior state changed')
    for m in [a,b]:
        if m['input_sha256'].get(str(inventory))!=sha(inventory):raise ValueError('actual executed driver inventory required')
        if m['controls']['actual_HS_INV2_inputs_driven'] is not True:raise ValueError('actual programming-driver inputs required')
    codes=[programming_sources(i['controls'],m['controls']['coarse'],m['controls']['fine']) for m in [a,b]]
    expected={n for n in codes[0] if codes[0][n]!=codes[1][n]}
    if not expected:raise ValueError('nonempty programming challenge required')
    x,y=[sources(p/'sources.spice') for p in [reference,target]]
    if x.keys()!=y.keys() or {n for n in x if x[n][1]!=y[n][1]}!=expected:raise ValueError('unexpected source changes')
    for actual,declared in zip([x,y],codes):
        if any(float(actual[n][1])!=v for n,v in declared.items()):raise ValueError('programming values differ from declared code')
    if (reference/'devices.spice').read_bytes()!=(target/'devices.spice').read_bytes():raise ValueError('physical cards changed')
    if canonical_deck((reference/'control.spice').read_text())!=canonical_deck((target/'control.spice').read_text()):raise ValueError('solver or observation protocol changed')
    files=[Path(__file__).resolve(),inventory]+[Path(__file__).with_name(n) for n in ['run_selected_dco_real_driver_control_v3.py','audit_selected_dco_history_inputs.py','compare_selected_dco_load_controls.py']]+[d/n for d in [reference,target] for n in ['manifest.json','devices.spice','sources.spice','control.spice']]
    save(output,dict(input_sha256={str(f):sha(f) for f in files},changed_physical_driver_input_nodes=sorted(expected),same_physical_cards=True,same_exterior_state=True,same_solver_and_observation_protocol=True,only_declared_programming_changed=True,frequency_correlation_qualified=False,release_ready=False));print('verified static programming changes',len(expected))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['reference','target','inventory','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['reference','target','inventory','output']))
