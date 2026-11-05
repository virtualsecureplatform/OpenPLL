#!/usr/bin/env python3
"""Map exact MOS gate-box matches in Magic antenna feedback to extracted nets.

This is diagnostic localization, not a unique count of all antenna violations.
Only exact rectangular gate matches inferred from extracted L/W are assigned.
Other feedback shapes and nonrectangular/device geometries remain unassigned.
"""
import argparse
from collections import Counter, defaultdict
from functools import lru_cache
import json
from pathlib import Path
import re

from check_compact_clock_tree import verify
from run_dco_qualification import sha, save


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('antenna','output'):
        parser.add_argument('--'+name,required=True,type=Path)
    args = parser.parse_args()
    source,out = args.antenna.resolve(),args.output.resolve()
    receipt = verify(source/'native_completion.json')
    assert receipt['exit_code'] == 0
    directory = source/'extraction'
    top = 'IntegerPLL_400MHz_CandidateTop'
    parents = {}

    def find(node):
        parents.setdefault(node,node)
        root = node
        while parents[root] != root:
            root = parents[root]
        while parents[node] != node:
            nxt = parents[node]
            parents[node] = root
            node = nxt
        return root

    def union(a,b):
        a,b = find(a),find(b)
        if a != b:
            parents[b] = a

    files = [Path(__file__).resolve(),source/'native_completion.json',source/'antenna_feedback.txt']

    @lru_cache(None)
    def read(name):
        path = directory/(name+'.ext')
        files.append(path)
        lines = path.read_text().splitlines()
        assert 'scale 1000 1 500000' in lines
        return lines

    boxes = defaultdict(list)
    visits = Counter()

    def point(t,x,y):
        a,b,c,d,e,f = t
        return a*x+b*y+c,d*x+e*y+f

    def walk(name,prefix,transform):
        visits[name] += 1
        for line in read(name):
            if line.startswith(('merge ','equiv ')):
                quoted = re.findall(r'"((?:\\.|[^"\\])*)"',line)
                assert len(quoted) >= 2
                union(prefix+quoted[0],prefix+quoted[1])
            elif line.startswith('device msubckt '):
                fields = line.split()
                quoted = re.findall(r'"((?:\\.|[^"\\])*)"',line)
                if not any(x in fields[2] for x in ('nfet','pfet')):
                    continue
                assert len(quoted) >= 4
                x,y = int(fields[3]),int(fields[4])
                length = int(re.search(r'\bl=(\d+)\b',line)[1])
                width = int(re.search(r'\bw=(\d+)\b',line)[1])
                assert length > 0 and width > 0
                p,q = point(transform,x,y),point(transform,x+length,y+width)
                box = (min(p[0],q[0]),min(p[1],q[1]),max(p[0],q[0]),max(p[1],q[1]))
                gate = prefix+quoted[1]
                find(gate)
                boxes[box].append(dict(instance=prefix.rstrip('/'),master=name,
                                      gate_node=gate,mos_type=fields[2]))
            elif line.startswith('use '):
                fields = line.split()
                assert len(fields)==9, line
                child,ident = fields[1:3]
                a,b,c,d,e,f = map(int,fields[3:])
                aa,bb,cc,dd,ee,ff = transform
                composed = (aa*a+bb*d,aa*b+bb*e,aa*c+bb*f+cc,
                            dd*a+ee*d,dd*b+ee*e,dd*c+ee*f+ff)
                walk(child,prefix+ident+'/',composed)

    walk(top,'',(1,0,0,0,1,0))
    aliases = defaultdict(set)
    for line in read(top):
        if line.startswith(('node ','port ')):
            name = re.match(r'\S+ "([^"]+)"',line)[1]
            aliases[find(name)].add(name)
    feedback = (source/'antenna_feedback.txt').read_text()
    rows = re.findall(r'box (-?\d+) (-?\d+) (-?\d+) (-?\d+)\nfeedback add "Antenna error at plane ([^\n]+)\n" pale',feedback)
    matched = []
    for *coords,plane in rows:
        box = tuple(map(int,coords))
        if box not in boxes:
            continue
        gates = boxes[box]
        roots = {find(row['gate_node']) for row in gates}
        matched.append(dict(box_internal_units=box,plane=plane,matched_gates=gates,
            extracted_net_roots=sorted(roots),top_node_aliases=sorted({a for root in roots for a in aliases[root]})))
    assert matched, 'no exact rectangular MOS gate localization'
    grouped = defaultdict(list)
    for index,row in enumerate(matched):
        for root in row['extracted_net_roots']:
            grouped[root].append(index)
    out.mkdir(parents=True,exist_ok=False)
    save(out/'gate_matches.json',matched)
    save(out/'localized_nets.json',{root:dict(top_node_aliases=sorted(aliases[root]),
        gate_match_indices=indices) for root,indices in grouped.items()})
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in files},
        artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()},
        extraction_instances_visited=sum(visits.values()),feedback_rectangles=len(rows),
        exact_rectangular_gate_feedback_matches=len(matched),
        distinct_extracted_nets_among_exact_matches=len(grouped),
        unmatched_feedback_rectangles=len(rows)-len(matched),
        coordinate_unit_um=0.005,all_violating_nets_identified=False,
        antenna_qualified=False,release_qualified=False,adopted=False,scope=__doc__))
    print(json.dumps(dict(gate_matches=len(matched),localized_nets=len(grouped),
        top_aliases=sorted({a for root in grouped for a in aliases[root]}))))


if __name__ == '__main__':
    main()
