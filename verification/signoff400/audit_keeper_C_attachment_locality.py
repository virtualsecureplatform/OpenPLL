"""Audit whether diagnostic conductor-wide C lifts retain cell-pin locality."""
import argparse,json,re
from fractions import Fraction
from pathlib import Path
from common_v3 import save,sha,verify
from build_prototype_full_C_wire_R_v5 import expand,rows
from prepare_prototype_analog_reference import subcircuits


def audit(text,top,spef,mapping,lift):
    blocks=subcircuits(text)
    _,_,_,aliases,_=expand(blocks,top)
    tokens={t['node'] for n in spef['nets'] for t in n['connections']}
    tokens.update(v for n in spef['nets'] for r in n['resistors'] for v in r['nodes'])
    primary={t['node'] for n in spef['nets'] for t in n['connections'] if t['kind']=='P'}
    wire={t:t if t in primary else top+'/__wire_'+str(i) for i,t in enumerate(sorted(tokens))}
    terminals={}
    for net in spef['nets']:
        for t in net['connections']:
            if t['kind']=='I':
                inst,pin=t['node'].rsplit(':',1)
                key=(mapping[re.sub(r'\\(.)',r'\1',inst)],pin)
                if key in terminals:raise ValueError('duplicate routed pin')
                terminals[key]=wire[t['node']]
    cache={}; result=[]
    root_ports=rows(blocks[top])[0].split()[2:]
    for line in rows(blocks[top])[1:-1]:
        f=line.split()
        if not f[0].upper().startswith('X') or f[-1] not in blocks:continue
        inst=f[0][1:];master=f[-1]
        if master not in cache:cache[master]=expand(blocks,master)
        ports,_,caps,local_aliases,_=cache[master]
        if len(ports)!=len(f[1:-1]):raise ValueError('cell arity mismatch')
        bindings=dict(zip(ports,f[1:-1]))
        for pin in ports:
            if (inst,pin) not in terminals:continue
            canonical=local_aliases.find(pin)
            touched=[v for (a,b),v in caps.items() if canonical in (a,b)]
            if not touched:continue
            original=bindings[pin]
            original=aliases.find(original if original in root_ports or original=='0' else top+'/'+original)
            if original not in lift:raise ValueError('missing diagnostic C voltage map')
            actual=terminals[inst,pin];chosen=lift[original]
            result.append(dict(instance=inst,master=master,pin=pin,
                local_capacitor_pairs=len(touched),absolute_incident_capacitance_f=str(sum(map(abs,touched),Fraction())),
                actual_cell_terminal=actual,diagnostic_C_terminal=chosen,
                locality_preserved=actual==chosen))
    if not result:raise ValueError('no cell-local capacitance endpoints audited')
    return result


def run(extraction,rc,binding,variant,output):
    receipts=[p/'assessment.json'for p in [extraction,rc,binding,variant]]
    records=[json.loads(p.read_text())for p in receipts]
    for r in records:verify(r['input_sha256']);verify(r['artifacts'])
    source=next(extraction.glob('*/capacitance.spice'));join=binding/'join.json';spef=rc/'nom.json'
    v=records[-1]
    for p in [source,join,spef]:
        if v['input_sha256'].get(str(p))!=sha(p):raise ValueError('model lineage differs')
    mapping={re.sub(r'\\(.)',r'\1',x['routed_instance']):x['extracted_instance']for x in json.loads(join.read_text())['mapping']}
    output.mkdir(parents=True,exist_ok=False);artifacts={};results=[];lifts=[]
    for attachment in ['driver','farthest']:
        lift=variant/('nom_'+attachment+'.lift.json');lifts.append(lift)
        if v['artifacts'].get(str(lift))!=sha(lift):raise ValueError('model lift differs')
        data=audit(source.read_text(),source.parent.name,json.loads(spef.read_text()),mapping,json.loads(lift.read_text()))
        target=output/(attachment+'.json');save(target,data);artifacts[str(target)]=sha(target)
        results.append(dict(attachment=attachment,cell_pin_C_endpoints=len(data),relocated_cell_pin_C_endpoints=sum(not row['locality_preserved']for row in data)))
    files=[Path(__file__).resolve(),Path(__file__).with_name('build_prototype_full_C_wire_R_v5.py'),source,join,spef,*receipts,*lifts]
    pins={str(p):sha(p)for p in files};verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,results=results,incident_capacitance_is_counted_per_pin_not_a_network_total=True,diagnostic_attachment_spread_is_not_a_physical_uncertainty_bound=True,spatial_capacitance_placement_qualified=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['extraction','rc','binding','variant','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve()for n in ['extraction','rc','binding','variant','output']))
