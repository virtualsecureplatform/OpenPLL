#!/usr/bin/env python3
"""Report resistive shortest-path bounds; not an IR-drop or settling proof."""
import argparse,hashlib,heapq,json,math
from pathlib import Path

def audit(path):
    graph={};terminals=set();resistors=[]
    for line in path.read_text().splitlines():
        t=line.split()
        if not t or t[0].startswith('*'):continue
        if t[0][0].lower()=='r':
            assert len(t)==4
            a,b=t[1].lower(),t[2].lower();r=float(t[3]);assert math.isfinite(r) and r>0
            graph.setdefault(a,[]).append((b,r));graph.setdefault(b,[]).append((a,r));resistors.append(r)
        elif t[0][0].lower()=='x':terminals.update(n.lower() for n in t[1:5])
    rails={}
    for rail in ['vpwr','vgnd','vpb','vnb']:
        targets={n for n in terminals if n==rail or n.startswith(rail+'.')}
        distances={rail:0.0};queue=[(0.0,rail)]
        while queue:
            d,n=heapq.heappop(queue)
            if d!=distances[n]:continue
            for other,r in graph.get(n,[]):
                trial=d+r
                if trial<distances.get(other,math.inf):distances[other]=trial;heapq.heappush(queue,(trial,other))
        reached={n:distances[n] for n in targets if n in distances}
        rails[rail]={'named_transistor_terminal_count':len(targets),'unreachable_named_terminals':sorted(targets-set(reached)),
                     'largest_shortest_path_ohm':max(reached.values(),default=None),
                     'largest_paths':sorted(reached.items(),key=lambda x:x[1],reverse=True)[:8]}
    return {'resistors':len(resistors),'resistors_above_1Mohm':sum(r>1e6 for r in resistors),'largest_resistor_ohm':max(resistors),'rails':rails}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--reduced',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();assert not a.output.exists()
    paths=[a.source,a.reduced,Path(__file__)]
    report={'source':audit(a.source),'reduced':audit(a.reduced),'sha256':{str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in paths},
            'scope':'Resistor-only connectivity and shortest-path upper bounds from named ideal rail ports to named transistor terminals. Large individual mesh resistors alone do not establish a slow rail. Does not measure effective resistance, nonlinear device paths, capacitance, dynamic rail voltage, all unlabeled terminals, or physical signoff.',
            'release_qualified':False,'selected':False}
    a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if __name__=='__main__':main()
