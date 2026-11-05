"""Extract three conventional parent wire views from an explicitly checked route."""
import argparse
import json
import os
from pathlib import Path
import re
import sys
import time
from common_v3 import ROOT,save,sha,verify
from prototype_spef_v2 import parse
from resources import lease
from compiled_charge import execute

OPENROAD=Path('/nix/store/qqz49dx8dpx4q9i5wriif091n7iaa0ld-openroad-2026-02-17/bin/openroad')

def check_network(net):
    parent={}
    def find(node):
        parent.setdefault(node,node)
        while parent[node]!=node:
            parent[node]=parent[parent[node]];node=parent[node]
        return node
    for resistor in net['resistors']:
        a,b=resistor['nodes'];parent[find(a)]=find(b)
    terminals=[c['node'] for c in net['connections']]
    if not terminals or len({find(node) for node in terminals})!=1:
        raise ValueError('parent wire terminals disconnected through resistors: '+net['name'])
    return dict(name=net['name'],terminals=len(terminals),resistors=len(net['resistors']),capacitors=len(net['capacitors']))

def run(route,power,frame,layout,lvs,output):
    sys.path.insert(0,str(ROOT/'verification/prototype400'))
    from prototype_candidate_parent_views_v2 import parent_views
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    views=parent_views(route,power,frame)
    lr=layout/'assessment.json';vr=lvs/'assessment.json'
    physical,matched=[json.loads(p.read_text()) for p in (lr,vr)]
    for record in (physical,matched):verify(record['input_sha256']);verify(record['artifacts'])
    if not physical['assembled_drc_pass'] or not matched['assembled_lvs_pass'] or matched['input_sha256'].get(str(lr))!=sha(lr) or physical['input_sha256'].get(str(route/'assessment.json'))!=sha(route/'assessment.json'):
        raise ValueError('matching assembled DRC and exact-alias LVS required')
    rules=ROOT/'build/timing450/pdk/sky130A/libs.tech/librelane'
    db=route/'route.odb';wires=route/'signal_wires.tsv'
    names={re.sub(r'\\(.)',r'\1',line) for line in wires.read_text().splitlines()}
    if not names:raise ValueError('routed signal inventory required')
    pins=dict(views['evidence_sha256'])
    paths=[lr,vr,db,wires,OPENROAD,Path(__file__).resolve(),Path(__file__).with_name('prototype_spef_v2.py'),Path(__file__).with_name('prototype_candidate_parent_views_v2.py')]
    pins.update({str(p):sha(p) for p in paths})
    output.mkdir(parents=True,exist_ok=False);artifacts={};results=[]
    os.environ.update(OMP_NUM_THREADS='4',OPENBLAS_NUM_THREADS='1',GOMAXPROCS='4')
    for corner in ('min','nom','max'):
        model=rules/f'rules.openrcx.sky130A.{corner}.magic';pins[str(model)]=sha(model)
        target=output/(corner+'.spef');script=output/(corner+'.tcl')
        script.write_text(f'read_db {{{db}}}\nset_thread_count 4\ndefine_process_corner -ext_model_index 0 RCX_{corner.upper()}\nextract_parasitics -ext_model_file {{{model}}} -corner 0\nwrite_spef {{{target}}}\nexit\n')
        pins[str(script)]=sha(script);verify(pins)
        save(output/'status.json',dict(state='extracting_parent_'+corner,release_ready=False))
        with lease(4,8,deadline):execute([OPENROAD,'-no_init','-exit',script],output/(corner+'.log'),deadline,8)
        parsed=parse(target.read_text())
        found={re.sub(r'\\(.)',r'\1',net['name']) for net in parsed['nets']}
        if found!=names or not parsed['pin_capacitance_excluded']:
            raise ValueError('parent SPEF net inventory or capacitance scope differs')
        networks=[check_network(net) for net in parsed['nets']]
        detail=output/(corner+'.json');save(detail,parsed)
        results.append(dict(corner=corner,networks=networks))
        artifacts.update({str(p):sha(p) for p in (target,detail,output/(corner+'.log'))})
    verify(pins);report=output/'networks.json';save(report,results);artifacts[str(report)]=sha(report)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,
         candidate_source_sha256=views['candidate_source_sha256'],parent_wire_views=['min','nom','max'],
         routed_signal_nets=len(names),all_wire_terminals_resistively_connected=True,
         all_SPEF_units_and_values_exactly_parsed=True,cell_pin_capacitance_excluded=True,
         native_macro_port_binding_complete=False,cell_and_parent_capacitance_combination_qualified=False,
         parent_loading_complete=False,release_ready=False))
    save(output/'status.json',dict(state='parent_wire_extraction_complete_binding_pending',release_ready=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('route','power','frame','layout','lvs','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();run(*(getattr(args,n).resolve() for n in ('route','power','frame','layout','lvs','output')))
