"""Require nodeset guesses only on newly internalized loads and preserve the native deck."""
import argparse,json,re
from pathlib import Path
from common_v3 import save,sha,verify
from compare_selected_dco_load_controls import canonical_deck


def run(reference,target,plan,output):
    if output.exists():raise FileExistsError(output)
    p=json.loads(plan.read_text());verify(p['input_sha256']);m=json.loads((target/'manifest.json').read_text());verify(m['input_sha256'])
    ancestors=[Path(x) for x in p['input_sha256'] if x.endswith('/selected_DCO_coherent_clock_halo_360.json')]
    if len(ancestors)!=1:raise ValueError('unique original private-node set required')
    original=set(json.loads(ancestors[0].read_text())['private_unknown_nodes']);expected=set(p['private_unknown_nodes'])-original
    values={};nodeset=target/'load_nodeset.spice'
    for line in nodeset.read_text().splitlines():
        match=re.fullmatch(r'\.NODESET V\(([^)]+)\)=([-+0-9.eE]+)',line)
        if not match or match[1] in values:raise ValueError('unique voltage guesses only')
        values[match[1]]=float(match[2])
    if set(values)!=expected or set(values)&original:raise ValueError('nodeset must cover only new internal load nodes')
    for name in ['devices.spice','sources.spice']:
        if (reference/name).read_bytes()!=(target/name).read_bytes():raise ValueError('physical circuit or stimuli changed')
    deck=(target/'control.spice').read_text();include=f'.include "{nodeset}"\n'
    if deck.count(include)!=1:raise ValueError('exactly one nodeset include required')
    deck=deck.replace(include,'')
    if canonical_deck((reference/'control.spice').read_text())!=canonical_deck(deck):raise ValueError('native solve controls changed beyond nodeset include')
    if re.search(r'(?im)^\s*\.ic\b|\bUIC\b|\bNOOP\b',deck):raise ValueError('unconstrained DC solve required')
    files=[Path(__file__).resolve(),plan,nodeset]+[d/n for d in [reference,target] for n in ['manifest.json','devices.spice','sources.spice','control.spice']]
    save(output,dict(input_sha256={str(x):sha(x) for x in files},new_load_nodeset_guesses=len(values),original_DCO_private_nodes_seeded=False,same_physical_circuit_and_sources=True,only_nodeset_include_added=True,UIC_or_NOOP_used=False,scope='recorded final-bias guesses for a new DC solve; state selection remains conditional',release_ready=False));print('new load guesses',len(values),'same circuit and stimuli')

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['reference','target','plan','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['reference','target','plan','output']))
