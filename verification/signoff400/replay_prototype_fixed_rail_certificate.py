"""Replay the fixed-rail capacitance certificate using only Python exact arithmetic."""
import argparse
from fractions import Fraction as F
import json
from pathlib import Path
from common import save,sha,verify


def replay(rows,weights):
    fixed='__fixed_rail_AC_reference'
    nodes={node for a,b,_ in rows for node in (a,b) if node!=fixed}
    if set(weights)!=nodes or any(type(w) is not int or w<=0 for w in weights.values()):
        raise ValueError('one strictly positive integer weight required for every free node')
    margins={node:F(0) for node in nodes}
    pairs=set()
    for a,b,value in rows:
        key=tuple(sorted((a,b)))
        if a==b or key in pairs:raise ValueError('aggregated distinct pairs required')
        pairs.add(key)
        if a!=fixed:
            margins[a]+=value*weights[a]
            if b!=fixed:margins[a]-=abs(value)*weights[b]
        if b!=fixed:
            margins[b]+=value*weights[b]
            if a!=fixed:margins[b]-=abs(value)*weights[a]
    return margins


def run(source,certificate,output):
    output.mkdir(parents=True,exist_ok=False)
    sr=source/'assessment.json';cr=certificate/'assessment.json'
    s,c=[json.loads(p.read_text()) for p in (sr,cr)]
    verify(s['artifacts']);verify(c['artifacts'])
    if c['input_sha256'].get(str(sr))!=sha(sr):raise ValueError('certificate source mismatch')
    pairfile=source/'dynamic.pairs.jsonl';proof=certificate/'weights.json';rows=[]
    for line in pairfile.open():
        r=json.loads(line);a,b=r['nodes'];rows.append((a,b,F(r['farads'])))
    weights=json.loads(proof.read_text());margins=replay(rows,weights['weights'])
    declared={n:F(v) for n,v in weights['exact_row_margins_F'].items()}
    if margins!=declared:raise ValueError('claimed exact margins differ from replay')
    passed=bool(margins) and all(v>0 for v in margins.values())
    paths=[sr,cr,pairfile,proof,Path(__file__).resolve()]
    save(output/'assessment.json',dict(input_sha256={str(p):sha(p) for p in paths},
        exact_certificate_replay_pass=passed,rows=len(margins),
        minimum_exact_margin_F=str(min(margins.values())),fixed_voltage_nodes=s['fixed_voltage_nodes'],
        unrestricted_supply_port_passivity_claimed=False,validated_for_prototype=False,release_ready=False))
    print('Exact certificate replay:',passed)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('source','certificate','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(a.source.resolve(),a.certificate.resolve(),a.output.resolve())
