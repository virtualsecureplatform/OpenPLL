#!/usr/bin/env python3
"""Audit all parent SPEF endpoints and export coupled parent-wire SPICE.

Wire capacitance excludes macro pin/internal capacitance and external pads.
Macro-interior cross-boundary coupling and extraction accuracy are unqualified.
Reported RC corners are PDK views, not proven load or delay bounds.
"""
import argparse
from collections import defaultdict
from decimal import Decimal
import heapq
import json
from pathlib import Path
import re

from check_compact_clock_tree import verify
from run_dco_qualification import sha, save


def unquote(value):
    return re.sub(r'\\(.)', r'\1', value)


def parse(path):
    text = path.read_text()
    for header in ('*C_UNIT 1 PF', '*R_UNIT 1 OHM', '"PIN_CAP NONE"', '*DELIMITER :'):
        assert header in text, header
    names = dict(re.findall(r'^(\*\d+) (\S+)$',
        text.split('*NAME_MAP\n', 1)[1].split('*PORTS', 1)[0], re.M))

    def decode(token):
        found = re.fullmatch(r'(\*\d+)(:.*)?', token)
        return unquote(names[found[1]]+(found[2] or '') if found else token)

    result = {}
    for key, total, body in re.findall(r'^\*D_NET (\*\d+) (\S+)\n(.*?)^\*END', text, re.M|re.S):
        name = decode(key)
        assert name not in result
        row = dict(endpoints={}, resistors=[], caps=[], total=Decimal(total))
        section = None
        for line in body.splitlines():
            f = line.split()
            if not f:
                continue
            if f[0] in ('*CONN', '*RES', '*CAP'):
                section = f[0]
                continue
            if section == '*CONN':
                assert f[0] in ('*I', '*P')
                node = decode(f[1])
                assert node not in row['endpoints']
                row['endpoints'][node] = (f[0][1:], f[2])
            elif section in ('*RES', '*CAP'):
                value = Decimal(f[-1])
                assert value.is_finite() and value >= 0
                if section == '*RES':
                    assert len(f) == 4
                    row['resistors'].append((decode(f[1]), decode(f[2]), value))
                else:
                    assert len(f) in (3, 4)
                    row['caps'].append((decode(f[1]), decode(f[2]) if len(f)==4 else None, value))
            else:
                raise AssertionError(line)
        result[name] = row
    return result


def validate(nets, expected):
    assert set(nets) == set(expected), (set(nets)-set(expected), set(expected)-set(nets))
    ownership = {}
    for name, row in nets.items():
        assert set(row['endpoints']) == set(expected[name]), name
        for node, (kind, direction) in expected[name].items():
            # This OpenRCX exporter writes INOUT as I. Preserve the original
            # database direction after checking this explicit representation.
            assert row['endpoints'][node] == (kind, 'I' if direction == 'B' else direction), (name, node)
        row['endpoints'] = expected[name].copy()
        graph = defaultdict(dict)
        for a, b, value in row['resistors']:
            graph[a][b] = min(value, graph[a].get(b, value))
            graph[b][a] = graph[a][b]
        local = set(row['endpoints']) | set(graph)
        for node in local:
            assert node not in ownership, (name, node)
            ownership[node] = name
        start = next(iter(row['endpoints']))
        seen, pending = {start}, [start]
        while pending:
            node = pending.pop()
            for other in graph[node].keys()-seen:
                seen.add(other)
                pending.append(other)
        assert local <= seen, (name, 'disconnected endpoint or RC island', local-seen)
        row['graph'] = graph
    couplings = defaultdict(list)
    for name, row in nets.items():
        capsum = Decimal(0)
        for a, b, value in row['caps']:
            assert a in ownership and ownership[a] == name or b in ownership and ownership[b] == name
            assert a in ownership and (b is None or b in ownership), (name, a, b)
            capsum += value
            if b is not None:
                assert a != b and ownership[a] != ownership[b], (name, a, b)
                couplings[tuple(sorted((a,b)))].append((name, value))
        assert abs(capsum-row['total']) <= max(Decimal('1e-8'), row['total']*Decimal('0.00001')), name
    for pair, occurrences in couplings.items():
        assert len(occurrences) == 2, (pair, occurrences)
        assert {name for name, _ in occurrences} == {ownership[n] for n in pair}
        assert occurrences[0][1] == occurrences[1][1], (pair, occurrences)
    return ownership, couplings


def summarize(name, row):
    distances = {}
    for source, (kind, direction) in row['endpoints'].items():
        if not (kind == 'I' and direction == 'O' or kind == 'P' and direction == 'I'):
            continue
        best, pending = {source: Decimal(0)}, [(Decimal(0), source)]
        while pending:
            distance, node = heapq.heappop(pending)
            if distance != best[node]:
                continue
            for other, value in row['graph'][node].items():
                trial = distance+value
                if other not in best or trial < best[other]:
                    best[other] = trial
                    heapq.heappush(pending, (trial, other))
        distances[source] = {node: str(best[node]) for node in row['endpoints'] if node != source}
    return dict(endpoints=row['endpoints'], resistor_count=len(row['resistors']),
        ground_capacitance_pf=str(sum((v for _,b,v in row['caps'] if b is None), Decimal(0))),
        incident_coupling_capacitance_pf=str(sum((v for _,b,v in row['caps'] if b is not None), Decimal(0))),
        reported_total_wire_capacitance_pf=str(row['total']),
        shortest_resistive_path_ohm=distances,
        shortest_path_is_not_effective_resistance_or_delay=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('extraction', 'output'):
        parser.add_argument('--'+name, required=True, type=Path)
    args = parser.parse_args()
    source, out = args.extraction.resolve(), args.output.resolve()
    receipt = verify(source/'assessment.json')
    assert receipt['parent_wire_rc_extracted']
    expected = defaultdict(dict)
    for line in (source/'connections_nom.tsv').read_text().splitlines():
        name, kind, inst, pin, direction = line.split('\t')
        name, pin = unquote(name), unquote(pin)
        node = inst+':'+pin if kind == 'I' else pin
        direction = dict(INPUT='I', OUTPUT='O', INOUT='B')[direction]
        assert node not in expected[name]
        expected[name][node] = (kind, direction)
    assert len(expected) == 357
    paths = [Path(__file__).resolve(), source/'assessment.json']
    paths += [source/f'route.{view}.spef' for view in ('nom','min','max')]
    paths += [source/f'connections_{view}.tsv' for view in ('nom','min','max')]
    pins = {str(p): sha(p) for p in paths}
    out.mkdir(parents=True, exist_ok=False)
    summaries = {}
    critical = ('PLLOUT', 'BBPD[0]', 'BBPD[1]', 'REFCLK', 'CLKDIV_RETIMED', 'BBPD_RESET_N', 'RESET_N')
    for view in ('nom','min','max'):
        nets = parse(source/f'route.{view}.spef')
        ownership, coupled = validate(nets, expected)
        endpoints = sorted({n for row in nets.values() for n in row['endpoints']})
        nodes = endpoints+sorted(set(ownership)-set(endpoints))
        symbols = {n: f'n{i:05d}' for i,n in enumerate(nodes)}
        lines = ['* Parent wires only; VGND is the capacitor reference.',
                 '* Include the matching three macro models and external loads separately.',
                 '.subckt PLL_PARENT_RC VGND']
        for i in range(0,len(endpoints),8):
            lines.append('+ '+' '.join(symbols[n] for n in endpoints[i:i+8]))
        rindex = cindex = 0
        for row in nets.values():
            for a,b,value in row['resistors']:
                rindex += 1
                lines.append(f'R{rindex} {symbols[a]} {symbols[b]} {value}')
            for a,b,value in row['caps']:
                if b is None and value:
                    cindex += 1
                    lines.append(f'C{cindex} {symbols[a]} VGND {value}p')
        for (a,b), occurrences in sorted(coupled.items()):
            value = occurrences[0][1]
            if value:
                cindex += 1
                lines.append(f'C{cindex} {symbols[a]} {symbols[b]} {value}p')
        lines += ['.ends PLL_PARENT_RC', '']
        (out/f'parent.{view}.spice').write_text('\n'.join(lines))
        save(out/f'bindings.{view}.json', dict(port_order=['VGND']+[symbols[n] for n in endpoints],
            boundary_node_to_spice={n:symbols[n] for n in endpoints}, node_to_net=ownership))
        rows = {name:summarize(name,row) for name,row in nets.items()}
        save(out/f'nets.{view}.json', rows)
        summaries[view] = dict(nets=len(nets), boundary_endpoints=len(endpoints),
            resistor_count=rindex, nonzero_spice_capacitors=cindex,
            reciprocal_coupling_pairs=len(coupled),
            critical_nets={name:rows[name] for name in critical})
    for path,digest in pins.items():
        assert sha(Path(path)) == digest, path
    save(out/'assessment.json', dict(input_sha256=pins,
        artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()},
        results=summaries, all_357_net_endpoint_sets_match_database=True,
        all_wire_graphs_connected=True, reciprocal_couplings_deduplicated=True,
        wire_capacitance_totals_reconciled=True, coupled_parent_spice_exported=True,
        pin_internal_and_external_loads_included=False, electrical_enclosure_qualified=False,
        physical_timing_qualified=False, release_qualified=False, adopted=False, scope=__doc__))
    print(json.dumps({view:r['critical_nets']['PLLOUT'] for view,r in summaries.items()}))


if __name__ == '__main__':
    main()
