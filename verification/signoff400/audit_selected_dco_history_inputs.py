"""Check that the history control retains the baseline circuit and solver deck."""
import argparse,json,re
from pathlib import Path
from common_v3 import save,sha,verify


def normalized_deck(folder,duration):
    text=(folder/'control.spice').read_text()
    for name in ['devices.spice','sources.spice','control.raw']:
        path=str(folder/name)
        if text.count(path)!=1:raise ValueError('unique native input/output reference required')
        text=text.replace(path,'<'+name+'>')
    card=f'.tran 10p {duration}n 0 10p'
    if text.splitlines().count(card)!=1:raise ValueError('declared native horizon and unchanged step required')
    return text.replace(card,'.tran 10p <duration> 0 10p')


def sources(path):
    result={}
    for line in path.read_text().splitlines():
        match=re.fullmatch(r'(V\S+) (\S+) 0 (.+)',line)
        if not match or match[2] in result:raise ValueError('independent boundary and rail voltage sources required')
        result[match[2]]=(match[1],match[3])
    return result


def compare_sources(base,target,history_nodes):
    if base.keys()!=target.keys():raise ValueError('boundary node inventory changed')
    changed={node for node in base if base[node]!=target[node]}
    if changed!=set(history_nodes):raise ValueError('only all 303 programming/reset sources may change')
    if any(not target[node][1].startswith('PWL FILE "') for node in changed):
        raise ValueError('recorded-history PWL sources required')
    if any(base[node][0]!=target[node][0] for node in changed):raise ValueError('voltage source identities changed')
    return sorted(changed)


def run(base,target,output):
    if output.exists():raise FileExistsError(output)
    manifests=[folder/'manifest.json' for folder in [base,target]]
    values=[json.loads(p.read_text()) for p in manifests]
    files=[*manifests,Path(__file__).resolve()]
    for folder,value in zip([base,target],values):
        for name in ['control.spice','devices.spice','sources.spice','exterior_final_voltages.json']:
            path=folder/name
            if value['input_sha256'].get(str(path))!=sha(path):raise ValueError('native input not pinned by manifest')
            files.append(path)
    if sha(base/'devices.spice')!=sha(target/'devices.spice'):raise ValueError('physical circuit changed')
    if sha(base/'exterior_final_voltages.json')!=sha(target/'exterior_final_voltages.json'):raise ValueError('quiet exterior snapshot changed')
    if normalized_deck(base,60)!=normalized_deck(target,260):raise ValueError('physics, tolerances or observation roles changed')
    a,b=values
    for key in ['observed_roles','selected_primitives','retained_passive_cards']:
        if a[key]!=b[key]:raise ValueError('physical control inventory changed')
    binaries=[p for p in a['input_sha256'] if p.endswith('/Xyce')]
    if len(binaries)!=1 or b['input_sha256'].get(binaries[0])!=a['input_sha256'][binaries[0]]:raise ValueError('native backend changed')
    history=target/'history_sources/assessment.json';h=json.loads(history.read_text())
    if b['input_sha256'].get(str(history))!=sha(history):raise ValueError('history construction receipt not pinned')
    records=h['sources'];nodes=[r['node'] for r in records.values()]
    if len(records)!=303 or len(set(nodes))!=303:raise ValueError('303 independent recorded inputs required')
    for role,r in records.items():
        if r['hold_after_ns']!=(None if role=='DCO_reset_driver_input' else 170):raise ValueError('history protocol changed')
        if r['union_knot_voltage_certificate'] is not True or r['maximum_voltage_difference_V']>1e-6 or r['uniform_voltage_bound_V']!=1e-6:raise ValueError('bounded voltage construction required')
    changed=compare_sources(sources(base/'sources.spice'),sources(target/'sources.spice'),nodes)
    files.append(history);pins={str(p):sha(p) for p in files};verify(pins)
    save(output,dict(input_sha256=pins,physical_circuit_identical=True,quiet_exterior_snapshot_identical=True,
        native_solver_and_tolerances_identical=True,observation_roles_identical=True,
        changed_voltage_source_nodes=changed,duration_ns=dict(base=60,target=260),
        change_scope='303 recorded programming/reset input histories and declared observation horizon',
        frequency_correlation_qualified=False,floating_charge_causality_proven=False,release_ready=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for name in ['base','target','output']:parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();run(args.base.resolve(),args.target.resolve(),args.output.resolve())
