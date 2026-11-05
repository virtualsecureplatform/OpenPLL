#!/usr/bin/env python3
"""Check routed DCO R graphs and exact DEF terminal identity at3 RC corners.

Keep multiple driver terminals explicit and report paths from each. Nets omitted
by SPEF must be unrouted singletons in DEF, not missing connected interconnect.
Name decoding is limited to explicit bracket/dot/backslash escapes and checked
for collisions. No capacitance distribution or timing qualification follows.
"""
from collections import defaultdict,Counter
import copy
import heapq
from pathlib import Path
import re
from audit_current_parent_wire_rc import parse
from check_bbpd_repair_identity import design
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT,sha,save


def canonical(name):
    value=re.sub(r'\\([.\[\]\\])',r'\1',name)
    assert '\\' not in value,repr(name)
    return value


def normalized(path):
    result={}
    for name,row in parse(path).items():
        key=canonical(name);assert key not in result
        terms={tuple(map(canonical,k)):(canonical(n),d,t) for k,(n,d,t) in row['terminals'].items()}
        coords={canonical(k):v for k,v in row['coordinates'].items()}
        assert len(terms)==len(row['terminals']) and len(coords)==len(row['coordinates'])
        result[key]=dict(terminals=terms,coordinates=coords,
            resistors=[(canonical(a),canonical(b),r) for a,b,r in row['resistors']])
    return result


def validate(nets,expected):
    assert nets.keys()<=expected.keys()
    rows={}
    for name,net in nets.items():
        assert set(net['terminals'])==expected[name],name
        graph=defaultdict(list)
        for a,b,r in net['resistors']:
            assert r>0;graph[a].append((b,r));graph[b].append((a,r))
        terms={n for n,d,k in net['terminals'].values()}
        assert terms<=graph.keys()<=net['coordinates'].keys(),name
        drivers=sorted(n for n,d,k in net['terminals'].values() if (k=='*I' and d=='O') or (k=='*P' and d=='I'))
        assert drivers,(name,net['terminals'])
        paths={}
        for source in drivers:
            distances={source:0.};queue=[(0.,source)]
            while queue:
                distance,node=heapq.heappop(queue)
                if distance!=distances[node]:continue
                for other,r in graph[node]:
                    if distance+r<distances.get(other,float('inf')):
                        distances[other]=distance+r;heapq.heappush(queue,(distance+r,other))
            assert set(distances)==set(graph),name
            paths[source]={n:distances[n] for n in sorted(terms)}
        rows[name]=dict(drivers=drivers,terminals=len(terms),nodes=len(graph),resistor_edges=len(net['resistors']),
            graph_is_tree=len(net['resistors'])==len(graph)-1,path_resistance_ohm_by_driver=paths,
            maximum_terminal_path_resistance_ohm=max(v for r in paths.values() for v in r.values()))
    return rows


def main():
    base=ROOT/'build/timing400/release_001';source=base/'current_DCO_intercell_wire_rc_001'
    verify(source/'native_completion.json')
    top='IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160'
    definition=ROOT/f'openlane/{top}/runs/c1fine_range_001/final/def/{top}.def'
    _,bindings,raw_nets=design(definition);expected=defaultdict(set)
    for key,name in bindings.items():
        if name not in ['VPWR','VGND']:expected[canonical(name)].add(tuple(map(canonical,key)))
    assert len(expected)==len({n for n in bindings.values() if n not in ['VPWR','VGND']})==958
    decoded_nets={canonical(k):v for k,v in raw_nets.items()};assert len(decoded_nets)==len(raw_nets)
    parsed={c:normalized(source/f'{c}.spef') for c in ['min','nom','max']}
    assert parsed['min'].keys()==parsed['nom'].keys()==parsed['max'].keys()
    missing=expected.keys()-parsed['nom'].keys()
    assert len(missing)==453 and all(len(expected[n])==1 for n in missing)
    assert all(not re.search(r'\+ (ROUTED|FIXED|COVER)',decoded_nets[n]) for n in missing)
    records={c:validate(nets,expected) for c,nets in parsed.items()}
    wrong=copy.deepcopy(parsed['nom']);name=next(iter(wrong));key=next(iter(wrong[name]['terminals']))
    wrong[name]['terminals'][('WRONG','PIN')]=wrong[name]['terminals'].pop(key)
    try:validate(wrong,expected)
    except AssertionError:pass
    else:raise AssertionError('wrong terminal accepted')
    inversions=[]
    for name,row in records['nom'].items():
        for driver,distances in row['path_resistance_ohm_by_driver'].items():
            for terminal in distances:
                lo,nom,hi=[records[c][name]['path_resistance_ohm_by_driver'][driver][terminal] for c in ['min','nom','max']]
                if not lo<=nom+1e-9<=hi+2e-9:inversions.append(dict(net=name,driver=driver,terminal=terminal,min=lo,nom=nom,max=hi))
    out=base/'DCO_intercell_wire_rc_audit_001';out.mkdir(exist_ok=False)
    save(out/'nets.json',records);save(out/'unrouted_singletons.json',sorted(missing))
    paths=[Path(__file__).resolve(),Path(__file__).with_name('audit_current_parent_wire_rc.py'),
        Path(__file__).with_name('check_bbpd_repair_identity.py'),source/'native_completion.json',definition,
        *[source/f'{c}.spef' for c in parsed]]
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in paths},
        artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()},
        DEF_signal_nets=958,routed_SPEF_nets_each_corner=len(parsed['nom']),unrouted_singleton_nets=453,
        all_multiterminal_DEF_nets_covered=True,all_SPEF_terminal_identities_match_DEF=True,
        all_R_graphs_connected=True,all_R_positive=True,coordinates_for_all_R_nodes=True,
        name_escape_decoding_collision_free=True,multiple_driver_nets=sum(len(r['drivers'])>1 for r in records['nom'].values()),
        path_corner_order_inversions=inversions,wrong_terminal_negative_control_rejected=True,
        generated_fill_C_and_intrinsic_pin_C_included=False,C_to_R_geometry_assignment_qualified=False,
        cell_internal_RC_included=False,full_RC_enclosure_qualified=False,physical_timing_qualified=False,
        release_qualified=False,adopted=False,scope=__doc__))
    print('DCO R audit:',len(parsed['nom']),'routed nets,453 unrouted singletons,',len(inversions),'path order inversions; all terminal identities/connectivity pass.')


if __name__=='__main__':main()
