"""Add explicit exterior source cuts where selected cell inputs lost their drivers."""
import argparse,json
from pathlib import Path
from common_v3 import save,sha,verify
from compare_prototype_physical_primitive_graphs import Union


def run(plan,audit,output):
    if output.exists():raise FileExistsError(output)
    p=json.loads(plan.read_text());a=json.loads(audit.read_text());verify(p['input_sha256']);verify(a['input_sha256'])
    if a['input_sha256'].get(str(plan))!=sha(plan):raise ValueError('matching actual input-drive audit required')
    model=next(Path(k) for k in p['input_sha256'] if Path(k).name=='model.spice');u=Union();ports=[]
    for line in model.open():
        f=line.split()
        if not f:continue
        if f[0][0].upper()=='R':u.join(f[1],f[2])
        elif f[0].lower()=='.subckt' and f[1]=='IntegerPLL_400MHz_PrototypeTop':ports=f[2:]
    if not ports:raise ValueError('actual top-level ports required')
    groups={}
    for r in a['unprescribed_input_pins_without_retained_output']:groups.setdefault(r['component'],[]).append(r)
    if not groups:raise ValueError('no missing input source boundaries')
    protected={u.find(r['node']) for r in p['protected_retained_outputs']};records=[]
    for root,rows in sorted(groups.items()):
        drivers={d['node'] for r in rows for d in r['physical_output_drivers'] if not d['retained']}
        if any(d['retained'] for r in rows for d in r['physical_output_drivers']):raise ValueError('retained output may not be voltage-prescribed')
        if drivers:
            if len(drivers)!=1:raise ValueError('ambiguous omitted physical output drivers')
            node=next(iter(drivers));origin='omitted physical cell output'
        else:
            candidates=[n for n in ports if u.find(n)==root]
            if len(candidates)!=1:raise ValueError('undriven input lacks unique actual top-level port')
            node=candidates[0];origin='actual top-level input port'
        if u.find(node)!=root or root in protected:raise ValueError('wrong driver component or retained output clamp')
        if node not in p['private_unknown_nodes']:raise ValueError('expected undriven private node')
        records.append(dict(node=node,component=root,origin=origin,affected_inputs=[{k:r[k] for k in ['cell_key','master','pin','node']} for r in rows]))
    cuts={r['node'] for r in records};private=set(p['private_unknown_nodes'])-cuts;boundary=set(p['required_non_supply_boundary_voltage_nodes'])|cuts
    p['private_unknown_nodes']=sorted(private);p['required_non_supply_boundary_voltage_nodes']=sorted(boundary)
    p['omitted_primitives_touching_private_nodes']={k:sorted(set(v)-cuts) for k,v in p['omitted_primitives_touching_private_nodes'].items() if set(v)-cuts}
    p['added_explicit_input_source_cuts']=records;p['external_input_histories_qualified']=False
    p['input_sha256'].update({str(plan):sha(plan),str(audit):sha(audit),str(Path(__file__).resolve()):sha(Path(__file__).resolve()),str(Path(__file__).with_name('compare_prototype_physical_primitive_graphs.py')):sha(Path(__file__).with_name('compare_prototype_physical_primitive_graphs.py'))})
    verify(p['input_sha256']);save(output,p);print('explicit input source cuts',len(cuts),'affected pins',sum(len(r['affected_inputs']) for r in records))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['plan','audit','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['plan','audit','output']))
