#!/usr/bin/env python3
"""Prepare the current event receiver with routed RC and conditional leaf loads.

Uses current transistor/cell RC models. Outside FF pin loads use supplied TT25
capacitances; omitted aggressors are static. Event reset is a separate ideal
cut, excluding its generation. This is a diagnostic fixture, not a qualified
load/noise/reset/metastability bound or a wholePLL model.
"""
import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import re

from characterize_compact_propagation import ROOT, SOURCE, SUPPLIES
from check_compact_clock_tree import verify
from check_compact_mapping import LIB
from run_dco_qualification import sha, save


def unquote(name):
    return re.sub(r'\\(.)', r'\1', name)


def spef(path):
    text = path.read_text()
    assert '*C_UNIT 1 PF' in text and '*R_UNIT 1 OHM' in text and '"PIN_CAP NONE"' in text
    names = {key: unquote(value) for key, value in re.findall(r'^(\*\d+) (\S+)$',
             text.split('*NAME_MAP\n',1)[1].split('*PORTS',1)[0], re.M)}

    def decode(token):
        m = re.fullmatch(r'(\*\d+)(:.*)?', token)
        return names[m[1]]+(m[2] or '') if m else unquote(token)

    blocks, endpoint = {}, {}
    for key, body in re.findall(r'^\*D_NET (\*\d+) ([\s\S]*?)^\*END', text, re.M):
        conn, resistors, caps = [], [], []
        section = None
        for line in body.splitlines()[1:]:
            f = line.split()
            if not f:
                continue
            if f[0] in ('*CONN','*CAP','*RES'):
                section = f[0]
                continue
            if section == '*CONN' and f[0] in ('*I','*P'):
                node = decode(f[1])
                assert node not in endpoint
                endpoint[node] = key
                conn.append(dict(kind=f[0],node=node,direction=f[2],
                    master=f[f.index('*D')+1] if '*D' in f else None))
            elif section == '*RES':
                assert len(f) == 4
                value = float(f[3]); assert math.isfinite(value) and value >= 0
                resistors.append((decode(f[1]),decode(f[2]),f[3]))
            elif section == '*CAP':
                assert len(f) in (3,4)
                value = float(f[-1]); assert math.isfinite(value) and value >= 0
                caps.append((decode(f[1]),decode(f[2]) if len(f)==4 else None,f[-1]))
        local = {c['node'] for c in conn}|{n for a,b,_ in resistors for n in (a,b)}
        blocks[key] = dict(name=names[key],conn=conn,resistors=resistors,caps=caps,local=local)
    return blocks, endpoint


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('route','equivalence','timing','output'):
        parser.add_argument('--'+name, required=True, type=Path)
    args = parser.parse_args()
    route, eq, timing, out = (getattr(args,k).resolve() for k in ('route','equivalence','timing','output'))
    assert not out.exists()
    rr, er, tr = (verify(p/'assessment.json') for p in (route,eq,timing))
    assert er['all_transition_and_output_functions_equivalent']
    assert tr['input_sha256'][str(route/'route.odb')] == sha(route/'route.odb')
    assert er['input_sha256'][str(route/'route.v')] == sha(route/'route.v')
    mapped = eq/'before_projection.json'
    assert sha(mapped) == er['artifacts'][str(mapped)]
    module = json.loads(mapped.read_text())['modules']['IntegerPLL_AcquiringCore']
    cells = module['cells']
    canonical = {}
    drivers = {}
    for name, cell in cells.items():
        n = unquote(name)
        assert n not in canonical, 'ambiguous cell quoting'
        canonical[n] = name
        for pin, direction in cell.get('port_directions',{}).items():
            if direction == 'output':
                for bit in cell['connections'][pin]:
                    if isinstance(bit,int):
                        assert bit not in drivers
                        drivers[bit] = (name,pin)
    cuts = {module['ports']['BBPD']['bits'][0]:'BBPD0',module['ports']['BBPD']['bits'][1]:'BBPD1',
            module['netnames']['core.bbpd_event_reset_n']['bits'][0]:'RESET_N'}
    roots = {name:module['netnames']['core.bbpd_'+direction+'_event_toggle']['bits'][0]
             for name,direction in (('UPQ','up'),('DNQ','dn'))}
    selected = set()

    def visit(bit):
        if bit in cuts:
            return
        assert isinstance(bit,int) and bit in drivers, ('unexpected cone boundary',bit)
        name, _ = drivers[bit]
        if name in selected:
            return
        selected.add(name)
        for pin, direction in cells[name]['port_directions'].items():
            if direction == 'input':
                for b in cells[name]['connections'][pin]:
                    visit(b)
    for bit in roots.values():
        visit(bit)
    sequential = [n for n in selected if '__dfrtp_' in cells[n]['type']]
    assert len(sequential) == 2 and {drivers[b][0] for b in roots.values()} == set(sequential)
    used_bits = {b for n in selected for bits in cells[n]['connections'].values() for b in bits}
    index_path = ROOT/'build/timing400/release_001/hs_cell_model_index_001/assessment.json'
    index = json.loads(index_path.read_text())['models']
    models = {}
    inputs = [Path(__file__).resolve(),mapped,route/'assessment.json',route/'route.v',
              eq/'assessment.json',timing/'assessment.json',index_path,LIB]
    unit = re.search(r'capacitive_load_unit\s*\(\s*([\d.]+)\s*,\s*"?(pf)"?\s*\)',
                     LIB.read_text(),re.I)
    assert unit and float(unit[1]) == 1.0
    for master in {cells[n]['type'] for n in selected}:
        entry = index[master]
        path = Path(entry['model'])
        assert sha(path) == entry['model_sha256']
        models[master] = entry
        inputs.append(path)
    pins = {str(p):sha(p) for p in inputs}
    out.mkdir(parents=True,exist_ok=False)
    results = []
    for rc in ('nom','min','max'):
        path = timing/f'route.{rc}.normalized.spef'
        pins[str(path)] = sha(path)
        blocks, endpoint = spef(path)
        bit_to_net = {}
        for name in selected:
            cell = cells[name]
            assert set(cell['connections']) == set(models[cell['type']]['ports'])-set(SUPPLIES)
            for pin, bits in cell['connections'].items():
                assert len(bits) == 1
                bit = bits[0]
                key = endpoint[unquote(name)+':'+pin]
                assert bit not in bit_to_net or bit_to_net[bit] == key
                bit_to_net[bit] = key
        assert set(bit_to_net) == used_bits and len(set(bit_to_net.values())) == len(used_bits)
        included = {key:blocks[key] for key in bit_to_net.values()}
        local = set().union(*(b['local'] for b in included.values()))
        aliases = {}
        for bit, alias in cuts.items():
            if alias.startswith('BBPD'):
                node = 'BBPD['+alias[-1]+']'
            else:
                name, pin = drivers[bit]
                node = unquote(name)+':'+pin
            assert endpoint[node] == bit_to_net[bit]
            aliases[node] = alias
        for alias, bit in roots.items():
            name,pin = drivers[bit]
            node = unquote(name)+':'+pin
            assert node not in aliases
            aliases[node] = alias
        outside, external_ports = [], []
        resistors, grounded, per_net_coupling = [], [], []
        coupling_tokens = {}
        net_metrics = []
        for bit, key in sorted(bit_to_net.items()):
            b = included[key]
            graph = defaultdict(set)
            for a,z,value in b['resistors']:
                graph[a].add(z);graph[z].add(a)
                resistors.append((a,z,value))
            connected = {b['conn'][0]['node']};pending=list(connected)
            while pending:
                for nxt in graph[pending.pop()]-connected:
                    connected.add(nxt);pending.append(nxt)
            assert {c['node'] for c in b['conn']} <= connected
            net_metrics.append(dict(logical_bit=bit,spef_net=b['name'],connections=len(b['conn']),
                                    wire_resistors=len(b['resistors']),all_endpoints_connected=True))
            for con in b['conn']:
                if con['kind'] == '*P':
                    external_ports.append(con)
                    continue
                instance,pin = con['node'].rsplit(':',1)
                name = canonical[instance]
                cell = cells[name]
                assert cell['connections'][pin] == [bit]
                assert con['direction'] == ('O' if cell['port_directions'][pin]=='output' else 'I')
                if con['master']:
                    assert con['master'] == cell['type']
                if name in selected:
                    continue
                if con['direction'] == 'O':
                    assert bit in cuts and drivers[bit] == (name,pin)
                    continue
                family=cell['type'].split('__')[1].rsplit('_',1)[0]
                source=SOURCE/family/(cell['type']+'__tt_025C_1v80_ccsnoise.lib.json')
                if not source.exists():source=SOURCE/family/(cell['type']+'__tt_025C_1v80.lib.json')
                data=json.loads(source.read_text())['pin,'+pin]
                values=[float(data[k]) for k in ('capacitance','rise_capacitance','fall_capacitance') if k in data]
                for k in ('rise_capacitance_range','fall_capacitance_range'):
                    if k in data:values.extend(map(float,data[k]))
                assert values and all(math.isfinite(v) and v>0 for v in values)
                pins[str(source)]=sha(source)
                outside.append(dict(instance=name,master=cell['type'],pin=pin,node=con['node'],
                                    capacitance_pf=max(values),view=str(source)))
            coupling = Counter()
            for a,z,value in b['caps']:
                if z is None:
                    assert a in b['local']
                    grounded.append((a,value))
                elif a in local and z in local:
                    identity=tuple(sorted((a,z)))+(float(value),)
                    coupling[identity]+=1;coupling_tokens[identity]=value
                else:
                    assert a in b['local'] or z in b['local']
                    grounded.append((a if a in b['local'] else z,value))
            per_net_coupling.append(coupling)
        merged = Counter()
        for counter in per_net_coupling:merged |= counter
        for node in sorted(local):aliases.setdefault(node,f'n{len(aliases):05d}')
        lines=['* Current compact receiver. Conditional TT25 leaf loads; static omitted aggressors.',
               *[f'.include "{models[m]["model"]}"' for m in sorted(models)],
               '.subckt bbpd_receiver BBPD0 BBPD1 RESET_N VGND VNB VPB VPWR UPQ DNQ PARAMS: LEAF_SCALE=1']
        selected_records=[]
        for i,name in enumerate(sorted(selected)):
            c=cells[name];master=c['type'];actual=[];bindings={}
            for pin in models[master]['ports']:
                if pin in SUPPLIES:actual.append(pin)
                else:
                    node=unquote(name)+':'+pin
                    actual.append(aliases[node]);bindings[pin]=aliases[node]
            lines.append(f'Xcell{i} '+' '.join(actual)+' '+master)
            selected_records.append(dict(instance=name,master=master,spice_instance=f'Xcell{i}',bindings=bindings))
        for i,(a,z,value) in enumerate(resistors):lines.append(f'Rwire{i} {aliases[a]} {aliases[z]} {value}')
        for i,(node,value) in enumerate(grounded):lines.append(f'Cground{i} {aliases[node]} VGND {value}p')
        i=0
        for (a,z,value),count in sorted(merged.items()):
            for _ in range(count):
                lines.append(f'Ccoupled{i} {aliases[a]} {aliases[z]} {coupling_tokens[a,z,value]}p');i+=1
        for i,entry in enumerate(outside):
            lines.append(f'Cleaf{i} {aliases[entry["node"]]} VGND {{LEAF_SCALE * {entry["capacitance_pf"]*1e-12:.17g}}}')
        lines.append('.ends bbpd_receiver')
        fixture=out/f'receiver.{rc}.spice';fixture.write_text('\n'.join(lines)+'\n')
        results.append(dict(rc=rc,fixture=str(fixture),selected_cells=selected_records,
            net_metrics=net_metrics,external_pin_capacitances=outside,external_ports=external_ports,
            wire_resistors=len(resistors),ground_caps=len(grounded),coupling_caps=sum(merged.values())))
    for name,digest in pins.items():assert sha(name)==digest,name
    save(out/'assessment.json',dict(input_sha256=pins,
        artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()},results=results,
        selected_cell_count=len(selected),selected_master_counts=dict(Counter(cells[n]['type'] for n in selected)),
        raw_capture_state_elements=2,logical_cut_bits=cuts,observed_state_bits=roots,
        native_simulations_added=0,outside_leaf_load_view='supplied TT25 scalar/range maximum only',
        omitted_aggressors_assumed_static=True,event_reset_generation_included=False,
        receiver_fixture_native_validated=False,effective_load_enclosure_qualified=False,
        metastability_qualified=False,physical_timing_qualified=False,release_qualified=False,scope=__doc__))
    print(f'Prepared{len(selected)}current receiver cells and3routedRC fixtures; conditional loads only')


if __name__ == '__main__':
    main()
