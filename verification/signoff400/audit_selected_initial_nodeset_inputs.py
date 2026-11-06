"""Verify all-node starting guesses against the retained initial native DC vector."""
import argparse,json,math,re
from pathlib import Path
from common_v3 import save,sha,verify
from compare_selected_dco_load_controls import canonical_deck
from check_selected_boundary_waveforms import bind


def run(reference,target,plan,snapshot,output):
    if output.exists():raise FileExistsError(output)
    p=json.loads(plan.read_text());s=json.loads((snapshot/'assessment.json').read_text());m=json.loads((target/'manifest.json').read_text());verify(p['input_sha256']);verify(s['artifacts']);verify(m['input_sha256'])
    vector=snapshot/'initial_voltage_vector.json'
    if s['artifacts'].get(str(vector))!=sha(vector) or m['input_sha256'].get(str(vector))!=sha(vector):raise ValueError('same verified native starting vector required')
    initial=json.loads(vector.read_text())
    if initial['time_s']!=0 or m['operating_point']['corner']!='tt':raise ValueError('TT initial DC state required')
    expected=set(p['private_unknown_nodes']);bindings=bind(expected,initial['variable_names'])
    if not bindings['all_bound']:raise ValueError('all private nodes need native initial values')
    nodeset=target/'initial_nodeset.spice';values={}
    for line in nodeset.read_text().splitlines():
        match=re.fullmatch(r'\.NODESET V\(([^)]+)\)=([-+0-9.eE]+)',line)
        if not match or match[1] in values:raise ValueError('unique voltage guesses only')
        values[match[1]]=float(match[2])
    if set(values)!=expected:raise ValueError('exact private-node guess coverage required')
    if any(not math.isfinite(v) or v!=initial['values'][bindings['bindings'][n]['index']] for n,v in values.items()):raise ValueError('guess differs from recorded initial voltage')
    for name in ['devices.spice','sources.spice']:
        if (reference/name).read_bytes()!=(target/name).read_bytes():raise ValueError('physical circuit or source protocol changed')
    deck=(target/'control.spice').read_text();include=f'.include "{nodeset}"\n'
    if deck.count(include)!=1:raise ValueError('exact nodeset include required')
    deck=deck.replace(include,'')
    if canonical_deck(deck)!=canonical_deck((reference/'control.spice').read_text()):raise ValueError('solver or transient observation protocol changed')
    if re.search(r'(?im)^\s*\.ic\b|\bUIC\b|\bNOOP\b',deck):raise ValueError('unconstrained DC solve required')
    files=[Path(__file__).resolve(),plan,snapshot/'assessment.json',vector,nodeset]+[d/n for d in [reference,target] for n in ['manifest.json','devices.spice','sources.spice','control.spice']]
    save(output,dict(input_sha256={str(p):sha(p) for p in files},all_private_node_guesses_match_initial_DC_vector=True,starting_voltage_guesses=len(values),same_physical_circuit_and_source_protocol=True,only_nodeset_include_added=True,UIC_or_NOOP_used=False,scope='new initial guesses only; actual unconstrained DC solution and state selection remain unqualified',release_ready=False));print('initial guesses verified',len(values),'same circuit and protocol')

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['reference','target','plan','snapshot','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['reference','target','plan','snapshot','output']))
