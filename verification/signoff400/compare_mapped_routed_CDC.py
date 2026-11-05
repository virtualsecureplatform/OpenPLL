"""Compare state source cones after resolving clock buffers, inverters and identifier escaping."""
import argparse
from functools import lru_cache
import json
from pathlib import Path
import re
from common import save,sha,verify


def identifier(name):
    # The routed writer escapes generated Yosys instance names a second time.
    stripped=name.lstrip('\\')
    return stripped if stripped.startswith('$auto$ff.cc:') else name


def clock_roots(module):
    drivers={};inputs={}
    for name,c in module['cells'].items():
        for pin,bits in c['connections'].items():
            if c['port_directions'][pin]=='output':
                for bit in bits:
                    if bit in drivers:raise ValueError('duplicate clock-cone driver')
                    drivers[bit]=(name,pin)
    for name,p in module['ports'].items():
        if p['direction']=='input':
            for index,bit in enumerate(p['bits']):inputs[bit]=(name,index)
    active=set()
    @lru_cache(None)
    def root(bit):
        if bit in inputs:return ('primary',*inputs[bit],0)
        if bit in active:raise ValueError('clock buffer cycle')
        if bit not in drivers:raise ValueError('undriven/constant clock leaf')
        name,pin=drivers[bit];c=module['cells'][name];kind=c['type']
        if re.fullmatch(r'sky130_fd_sc_hs__df[rs]tp_[124]',kind):
            if pin!='Q':raise ValueError('unreviewed sequential clock source')
            return ('sequential',identifier(name),pin,0)
        m=re.fullmatch(r'sky130_fd_sc_hs__(clkbuf|buf|clkinv|inv)_(1|2|4|8|16)',kind)
        if not m:raise ValueError('clock root has unreviewed logic: '+kind)
        incoming=[b for p,bits in c['connections'].items() if c['port_directions'][p]=='input' for b in bits]
        if len(incoming)!=1:raise ValueError('scalar clock buffer required')
        active.add(bit)
        try:r=root(incoming[0])
        finally:active.remove(bit)
        return (*r[:3],r[3]^(m[1] in ('clkinv','inv')))
    return root


def normalized(module,report):
    clock=clock_roots(module);states={};crossings=[]
    def origin(s):return (s['kind'],identifier(s['name']) if s['kind']=='sequential' else s['name'],
                         clock(s['clock_bit']) if s['kind']=='sequential' else s['port_index'])
    for r in report['sequential_state']:
        name=identifier(r['cell'])
        if name in states:raise ValueError('ambiguous normalized state identity')
        domain=clock(r['clock_bit'])
        states[name]=dict(clock_root=domain,control_pin=r['asynchronous_control_pin'],
             data_origins=sorted(origin(s) for s in r['data_sources']),control_origins=sorted(origin(s) for s in r['control_sources']))
        external=[origin(s) for s in r['data_sources'] if s['kind']=='primary_input' or clock(s['clock_bit'])!=domain]
        if external:crossings.append(dict(destination_cell=name,clock_root=domain,sources=sorted(external)))
    return states,crossings


def run(mapped,routed,output):
    output.mkdir(parents=True,exist_ok=False)
    receipts=[p/'assessment.json' for p in (mapped,routed)];a,b=[json.loads(p.read_text()) for p in receipts]
    source=next(Path(p) for p in a['input_sha256'] if p.endswith('/mapped.json'))
    target=routed/'routed.json';reports=[p/'inventory.json' for p in (mapped,routed)]
    paths=[*receipts,source,target,*reports,Path(__file__).resolve()];pins={str(p):sha(p) for p in paths}
    for p,expected in [(source,a['input_sha256'][str(source)]),(target,b['artifacts'][str(target)]),
                       (reports[0],a['artifacts'][str(reports[0])]),(reports[1],b['artifacts'][str(reports[1])])]:
        if pins[str(p)]!=expected:raise ValueError('mapped/routed CDC lineage mismatch')
    states=[];crossings=[]
    for p,q in zip((source,target),reports):
        s,c=normalized(json.loads(p.read_text())['modules']['IntegerPLL_ProgrammedCore'],json.loads(q.read_text()))
        states.append(s);crossings.append(c)
    missing=sorted(set(states[0])-set(states[1]));added=sorted(set(states[1])-set(states[0]))
    differences=[dict(cell=n,mapped=states[0][n],routed=states[1][n]) for n in sorted(set(states[0])&set(states[1])) if states[0][n]!=states[1][n]]
    report=output/'comparison.json';save(report,dict(missing_states=missing,added_states=added,changed_source_or_clock_cones=differences,
         mapped_normalized_crossings=crossings[0],routed_normalized_crossings=crossings[1]))
    verify(pins);save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(report):sha(report)},
         sequential_state_identities_match=not missing and not added,
         state_source_cones_and_clock_roots_match=not missing and not added and not differences,
         changed_source_or_clock_cones=len(differences),mapped_normalized_crossing_candidates=len(crossings[0]),
         routed_normalized_crossing_candidates=len(crossings[1]),
         clock_inversion_parity_retained=True,logic_function_equivalence_proved_by_this_check=False,
         physical_clock_relationships_qualified=False,complete_structural_inventory_qualified=False,
         final_GDS_connectivity_binding_qualified=False,physical_CDC_qualified=False,release_qualified=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('mapped','routed','output'):p.add_argument('--'+name,required=True,type=Path)
    a=p.parse_args();run(a.mapped.resolve(),a.routed.resolve(),a.output.resolve())
