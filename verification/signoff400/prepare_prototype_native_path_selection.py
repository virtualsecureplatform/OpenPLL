"""Recover a reported data path and both complete combinational clock cones."""
import argparse,json,re
from collections import defaultdict
from pathlib import Path
from common_v3 import save,sha,verify


def identifier(name):return name.lstrip('\\')


def select(module,states,report,start,end):
    cells=module['cells'];lookup={identifier(n):n for n in cells}
    if len(lookup)!=len(cells):raise ValueError('ambiguous routed instance names')
    matches=[]
    for block in report.split('Startpoint: ')[1:]:
        endpoint=re.search(r'^Endpoint: ([^\n]+)',block,re.M)
        if block.splitlines()[0].strip()==start and endpoint and endpoint[1].strip()==end and 'Path Type: min' in block:matches.append(block)
    if not matches:raise ValueError('requested minimum-delay path not reported')
    # Repeated groups must describe the same ordered data path.
    paths=[]
    for block in matches:
        ordered=[]
        for line in block.split('data arrival time')[0].splitlines():
            hit=re.search(r'[\^v] (\S+)/(\S+) \(',line)
            if hit:
                name=lookup.get(identifier(hit[1]))
                if name is None:raise ValueError('STA data-path instance absent from routed module')
                if not ordered or name!=ordered[-1]:ordered.append(name)
        paths.append(ordered)
    if any(p!=paths[0] for p in paths) or not paths[0]:raise ValueError('ambiguous reported data path')
    data=paths[0];sequential={identifier(s['cell']) for s in states}
    if identifier(data[0])!=start or identifier(data[-1])!=end or not {start,end}<=sequential:
        raise ValueError('reported sequential endpoints differ')
    selected=set(data);drivers=defaultdict(list);loads=defaultdict(list)
    for name,cell in cells.items():
        for pin,bits in cell['connections'].items():
            for bit in bits:
                (drivers if cell['port_directions'][pin]=='output' else loads)[bit].append((name,pin))
    clock_boundaries={};clock_cells=set();clock_paths={}
    for endpoint in (data[0],data[-1]):
        clock=cells[endpoint]['connections']['CLK']
        if len(clock)!=1:raise ValueError('scalar sequential clock required')
        pending=list(clock);visited=set();local=[]
        while pending:
            bit=pending.pop()
            if bit in visited:continue
            visited.add(bit)
            if isinstance(bit,str):raise ValueError('constant clock source')
            sources=drivers[bit]
            if not sources:
                primary=[p for p,v in module['ports'].items() if v['direction']=='input' and bit in v['bits']]
                if len(primary)!=1:raise ValueError('unique primary clock boundary required')
                clock_boundaries[bit]=dict(kind='primary_input',port=primary[0]);continue
            if len(sources)!=1:raise ValueError('multiple clock drivers')
            name,pin=sources[0]
            if identifier(name) in sequential:
                clock_boundaries[bit]=dict(kind='sequential_output',instance=name,pin=pin);continue
            if name in data:raise ValueError('data/clock combinational cones overlap')
            clock_cells.add(name);selected.add(name);local.append(name)
            for p,bs in cells[name]['connections'].items():
                if cells[name]['port_directions'][p]=='input':pending.extend(bs)
        clock_paths[endpoint]=local
    incident={b for name in selected for bs in cells[name]['connections'].values() for b in bs}
    boundary=[]
    for bit in sorted(incident,key=str):
        if isinstance(bit,str) or not drivers[bit] or all(n not in selected for n,p in drivers[bit]):boundary.append(bit)
    omitted=[dict(bit=b,instance=n,pin=p) for b in sorted(incident,key=str) for n,p in loads[b] if n not in selected]
    return dict(cells=sorted(selected),data_path=data,clock_cells=sorted(clock_cells),clock_paths=clock_paths,
        clock_boundaries=[dict(bit=b,**v) for b,v in sorted(clock_boundaries.items())],
        boundary_bits=boundary,omitted_receiver_terminals=omitted,
        analog_side_input_stimuli_justified=False,omitted_pin_loads_included=False)


def run(inventory,screen,start,end,output):
    ir=inventory/'assessment.json';sr=screen/'assessment.json';routed=inventory/'routed.json';state=inventory/'inventory.json';log=screen/'fixed_divide16/screen.log'
    a,b=[json.loads(p.read_text()) for p in (ir,sr)]
    verify(a['artifacts']);verify(b['artifacts'])
    # Both inventories and reports must descend from the same exact route proof.
    lineage={p:h for p,h in a['input_sha256'].items() if p.endswith('/assessment.json') and 'equivalence' in p}
    if len(lineage)!=1 or any(b['input_sha256'].get(p)!=h for p,h in lineage.items()):raise ValueError('routed path/proof lineage mismatch')
    module=json.loads(routed.read_text())['modules']['IntegerPLL_ProgrammedCore']
    selected=select(module,json.loads(state.read_text())['sequential_state'],log.read_text(),start,end)
    paths=[ir,sr,routed,state,log,Path(__file__).resolve()];pins={str(p):sha(p) for p in paths};verify(pins)
    output.mkdir(parents=True,exist_ok=False);detail=output/'selection.json';save(detail,selected)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},
        selected_cells=len(selected['cells']),data_path_cells=len(selected['data_path']),clock_cells=len(selected['clock_cells']),
        both_endpoint_clock_cones_recovered_to_explicit_boundaries=True,
        native_path_model_prepared=False,native_path_correlation_complete=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('inventory','screen','output'):p.add_argument('--'+name,type=Path,required=True)
    for name in ('start','end'):p.add_argument('--'+name,required=True)
    a=p.parse_args();run(a.inventory.resolve(),a.screen.resolve(),a.start,a.end,a.output.resolve())
