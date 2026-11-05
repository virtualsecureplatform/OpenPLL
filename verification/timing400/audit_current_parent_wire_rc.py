#!/usr/bin/env python3
"""Check current parent SPEF topology against DEF at all three RC corners.

Report minimum-resistance paths, not effective RC delay or timing qualification.
OpenRCX excludes generated GDS fill and uses its default 0.1fF coupling threshold.
"""
from collections import defaultdict
import copy
import heapq
from pathlib import Path
import re
from check_bbpd_repair_identity import design
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT, sha, save


def parse(path):
    names = {}
    nets = {}
    mode = None
    current = None
    def resolve(token):
        match = re.match(r'^\*(\d+)(.*)$', token)
        return names[match[1]] + match[2] if match else token
    for line in path.read_text().splitlines():
        f = line.split()
        if not f:
            continue
        if f[0] == '*NAME_MAP':
            mode = 'names'
        elif mode == 'names' and re.fullmatch(r'\*\d+', f[0]):
            names[f[0][1:]] = f[1]
        elif f[0] == '*D_NET':
            mode = 'net'
            name = resolve(f[1])
            assert name not in nets
            current = dict(terminals={}, coordinates={}, resistors=[], capacitance_pf=float(f[2]))
            nets[name] = current
        elif f[0] in ['*CONN','*CAP','*RES']:
            mode = f[0]
        elif mode == '*CONN' and f[0] in ['*I','*P','*N']:
            node = resolve(f[1])
            if f[0] != '*N':
                key = tuple(node.split(':',1)) if f[0] == '*I' else ('PIN',node)
                assert key not in current['terminals']
                current['terminals'][key] = (node,f[2],f[0])
            assert '*C' in f
            at = f.index('*C')
            current['coordinates'][node] = [float(x) for x in f[at+1:at+3]]
        elif mode == '*RES' and f[0].isdigit():
            a,b = map(resolve,f[1:3])
            resistance = float(f[3])
            assert resistance > 0
            current['resistors'].append((a,b,resistance))
        elif f[0] == '*END':
            current = None
            mode = None
    assert '*R_UNIT 1 OHM' in path.read_text() and '*C_UNIT 1 PF' in path.read_text()
    return nets


def validate(nets, bindings):
    expected = defaultdict(set)
    for key, net in bindings.items():
        if net not in ['VPWR','VGND']:
            expected[net].add(key)
    assert set(nets) == set(expected) and len(nets) == 357
    records = {}
    for name, net in nets.items():
        assert set(net['terminals']) == expected[name], name
        graph = defaultdict(list)
        for a,b,r in net['resistors']:
            graph[a].append((b,r))
            graph[b].append((a,r))
        terms = {value[0] for value in net['terminals'].values()}
        assert terms <= set(graph) <= set(net['coordinates']), name
        # A connected graph is necessary even if an extracted routing loop
        # exists. Dijkstra distances remain path resistance, not equivalent R.
        driver = [node for node,direction,kind in net['terminals'].values()
            if (kind=='*I' and direction=='O') or (kind=='*P' and direction=='I')]
        assert len(driver)==1, (name,driver)
        distances = {driver[0]:0.0}
        queue = [(0.0,driver[0])]
        while queue:
            distance,node = heapq.heappop(queue)
            if distance != distances[node]:
                continue
            for other,r in graph[node]:
                value = distance+r
                if value < distances.get(other,float('inf')):
                    distances[other]=value
                    heapq.heappush(queue,(value,other))
        assert set(distances)==set(graph), name
        records[name] = dict(terminals=len(terms), resistor_edges=len(net['resistors']), nodes=len(graph),
            graph_is_tree=len(net['resistors'])==len(graph)-1,
            extracted_wire_capacitance_pf=net['capacitance_pf'], source=driver[0],
            minimum_path_resistance_ohm={node:distances[node] for node in sorted(terms)},
            maximum_terminal_path_resistance_ohm=max(distances[node] for node in terms))
    return records


def main():
    base = ROOT/'build/timing400/release_001'
    source = base/'current_parent_wire_rc_001'
    verify(source/'native_completion.json')
    route = base/'parent_dco_antenna_targeted_011/route.def'
    _,bindings,_ = design(route)
    parsed = {corner:parse(source/f'{corner}.spef') for corner in ['min','nom','max']}
    records = {corner:validate(nets,bindings) for corner,nets in parsed.items()}
    wrong = copy.deepcopy(parsed['nom'])
    first = next(iter(wrong['BBPD_RESET_N']['terminals']))
    wrong['BBPD_RESET_N']['terminals'][('WRONG_INSTANCE','WRONG_PIN')] = wrong['BBPD_RESET_N']['terminals'].pop(first)
    rejected = False
    try:
        validate(wrong,bindings)
    except AssertionError:
        rejected = True
    assert rejected
    inversions = []
    for net in records['nom']:
        for term in records['nom'][net]['minimum_path_resistance_ohm']:
            low,nominal,high = [records[c][net]['minimum_path_resistance_ohm'][term] for c in ['min','nom','max']]
            if not low <= nominal+1e-9 <= high+2e-9:
                inversions.append(dict(net=net,terminal=term,min=low,nom=nominal,max=high))
    out = base/'current_parent_wire_rc_audit_001'
    out.mkdir(exist_ok=False)
    save(out/'nets.json', records)
    paths = [Path(__file__).resolve(),source/'native_completion.json',route,*[source/f'{c}.spef' for c in parsed]]
    save(out/'assessment.json', dict(input_sha256={str(p):sha(p) for p in paths},
        artifacts={str(out/'nets.json'):sha(out/'nets.json')}, rc_corners=list(parsed),
        signal_nets_each_corner=357, all_def_terminals_matched=True, all_resistance_graphs_connected=True,
        all_resistors_positive=True, coordinates_present_for_every_resistance_node=True,
        wrong_terminal_negative_control_rejected=True, terminal_path_corner_order_inversions=inversions,
        graph_tree_counts={c:sum(row['graph_is_tree'] for row in rows.values()) for c,rows in records.items()},
        default_small_coupling_grounding_threshold_ff=0.1, spef_pin_capacitance_included=False,
        generated_gds_fill_included=False, macro_internal_rc_included=False,
        geometry_to_native_capacitance_node_mapping_qualified=False, full_rc_enclosure_qualified=False,
        path_resistances_are_timing_delays=False, physical_timing_qualified=False,
        release_qualified=False, adopted=False, scope=__doc__))
    print('357 DEF nets and all resistance terminals connected at all3RC corners; path-order inversions:',len(inversions))


if __name__ == '__main__':
    main()
