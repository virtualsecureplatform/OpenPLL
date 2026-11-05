"""Trace changed source geometry to native zero-width terminal/node fallback data."""
import argparse
from collections import Counter,defaultdict
from fractions import Fraction as F
import json
from pathlib import Path
import re
import time
from common import save,sha
from audit_native_device_parameter_delta import number
from resources import lease


def run(extraction,delta,output):
    extraction,delta,out=(p.resolve() for p in (extraction,delta,output))
    out.mkdir(parents=True,exist_ok=False)
    domain=(extraction/'domain').resolve()
    receipts=[domain/'assessment.json',delta/'assessment.json']
    dom,prior=[json.loads(p.read_text()) for p in receipts]
    ext,trace=(domain/'trace'/n for n in ('Prototype400_FilledCapacitanceView.ext','SPICE_devices.log'))
    cards=delta/'native_device_cards.jsonl'
    differences=delta/'parameter_differences.jsonl'
    writer=next(Path(p) for p in dom['input_sha256'] if p.endswith('/assessment.json') and 'magic_device_interface_build' in p)
    build=json.loads(writer.read_text())
    source=Path(build['source'])/'ext2spice/ext2spice.c'
    paths=[*receipts,ext,trace,cards,differences,writer,source,Path(__file__).resolve(),
           Path(__file__).with_name('audit_native_device_parameter_delta.py')]
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    with lease(2,8,deadline):
        pins={str(p):sha(p) for p in paths}
        for p in (ext,trace):
            if pins[str(p)]!=dom['artifacts'][str(p)]:
                raise ValueError('native EXT/trace source changed')
        for p in (cards,differences):
            if pins[str(p)]!=prior['artifacts'][str(p)]:
                raise ValueError('complete native parameter delta changed')
        if 'area = node->efnode_pa[resClass].pa_area;' not in source.read_text():
            raise ValueError('native whole-node geometry fallback source changed')
        changed={r['instance']:r for r in map(json.loads,differences.read_text().splitlines())}
        pairs={}
        with cards.open() as stream:
            for line in stream:
                name,a,b=json.loads(line)
                if name in changed:
                    pairs[name]=(a,b)
        coordinates={}
        with trace.open() as stream:
            for lineno,line in enumerate(stream):
                fields=line.split('"')
                name=fields[0].split()[1]
                if name=='X0' and lineno:
                    break
                if name in changed:
                    coords=list(map(int,fields[2].split()))
                    coordinates[(fields[1],*coords[:2])]=(name,coords)
        nodes,selected={},{}
        implicit=[]
        explicit=defaultdict(lambda:[0,0])
        with ext.open() as stream:
            for lineno,line in enumerate(stream):
                if lineno%100000==0 and time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:
                    raise TimeoutError('junction fallback inventory deadline')
                if line.startswith(('node "VGND"','substrate "VGND"','node "VPWR"')):
                    _,name,tail=line.split('"',2)
                    values=list(map(int,tail.split()[5:]))
                    if len(values)%2:
                        raise ValueError('native node area/perimeter class pairs')
                    nodes[name]=list(zip(values[::2],values[1::2]))
                if not line.startswith('device '):
                    continue
                fields=re.split(r'"([^"]*)"',line)
                head=fields[0].split()
                model=head[2]
                if 'fet_' not in model:
                    continue
                key=(model,int(head[3]),int(head[4]))
                if key in coordinates:
                    selected[key]=fields
                kind='p' if 'pfet_' in model else 'n'
                for ix,terminal in ((5,'source'),(7,'drain')):
                    node=fields[ix]
                    tail=fields[ix+1].split()
                    ap=re.search(r'(-?\d+),(-?\d+)$',tail[-1])
                    if ap:
                        a,p=map(int,ap.groups())
                        explicit[node,kind][0]+=a
                        explicit[node,kind][1]+=p
                    else:
                        implicit.append(dict(model=model,point_internal=list(key[1:]),terminal=terminal,
                            original_conductor=node,original_bulk_conductor=fields[1],
                            terminal_edge_length=int(tail[0]),terminal_attributes=tail[-1]))
        implicit_file=out/'implicit_terminals.jsonl'
        implicit_file.write_text(''.join(json.dumps(r)+'\n' for r in implicit))
        cases=[]
        for key,(name,coords) in coordinates.items():
            fields=selected[key]
            before,after=pairs[name]
            params=dict(t.split('=',1) for t in before[before.index(key[0])+1:])
            grid=F(number(params['w']))/coords[5]
            if F(number(params['l']))!=coords[4]*grid:
                raise ValueError('independent native L/W grid scaling differs')
            source_tail=fields[6].split()
            if source_tail!=['0','0'] or fields[5]!=fields[1]:
                raise ValueError('changed terminal must be zero-width source on original bulk node')
            area,perim=F(number(params['as'])),F(number(params['ps']))
            matches=[]
            for index,(a,p) in enumerate(nodes[fields[5]]):
                if abs(a*grid*grid-area)<=abs(area)*F(1,100000) and abs(p*grid-perim)<=abs(perim)*F(1,100000):
                    matches.append(index)
            if len(matches)!=1:
                raise ValueError('changed source parameters do not identify a unique whole-node fallback class')
            rc=matches[0]
            cases.append(dict(instance=name,model=key[0],point_internal=list(key[1:]),
                 original_source_and_bulk_node=fields[5],original_source_terminal_edge_length=0,
                 original_source_attributes='0',matching_native_resistance_class=rc,
                 native_node_area_perimeter=list(nodes[fields[5]][rc]),
                 native_SPICE_length_units_per_internal_grid=str(grid),
                 predicted_whole_node_area=str(nodes[fields[5]][rc][0]*grid*grid),
                 predicted_whole_node_perimeter=str(nodes[fields[5]][rc][1]*grid),
                 original_parameter_tokens={k:params[k] for k in ('as','ps')},
                 post_R_parameters=changed[name]['differences']))
        if len(cases)!=prior['changed_parameter_devices']:
            raise ValueError('all changed parameter devices must be traced')
        data=out/'whole_node_fallback_cases.json'
        save(data,cases)
        all_zero=all(r['terminal']=='source' and r['terminal_edge_length']==0 and r['terminal_attributes']=='0' for r in implicit)
        all_bulk=all(r['original_conductor']==r['original_bulk_conductor'] for r in implicit)
        if any(sha(Path(p))!=h for p,h in pins.items()):
            raise ValueError('junction fallback inventory source changed')
        save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in (data,implicit_file)},
             all_changed_native_parameter_devices_traced_to_whole_node_fallback=True,
             changed_device_cases=len(cases),implicit_terminal_count=len(implicit),
             implicit_terminal_model_counts=dict(Counter(r['model'] for r in implicit)),
             all_implicit_terminals_are_zero_width_sources=all_zero,
             all_implicit_original_source_and_bulk_nodes_identical=all_bulk,
             explicit_terminal_attribute_area_perimeter_by_node_and_polarity={
                 node+':'+kind:values for (node,kind),values in explicit.items() if node in ('VGND','VPWR')},
             physical_spatial_junction_allocation_qualified=False,
             ideal_node_electrical_equivalence_probed=False,
             runtime_model_eligible=False,physical_RC_qualified=False,release_qualified=False))
        print(json.dumps(dict(changed_cases=len(cases),implicit_terminals=len(implicit),
             all_zero_width_sources=all_zero,all_original_source_bulk_nodes_alias=all_bulk)))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('extraction','delta','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    a=parser.parse_args()
    run(a.extraction,a.delta,a.output)
