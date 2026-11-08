"""Resolve selected-side nodes and exact capacitance totals for non-control-port crossings."""
import argparse,json,shlex
from collections import Counter,defaultdict
from fractions import Fraction as F
from pathlib import Path
from common_v3 import save,sha,verify
from audit_keeper_flat_MOS_region_join import Aliases
from audit_keeper_DCO_driver_C_cut import capacitance
from native_spice_comments import strip_floating_annotation

def run(cut,boundary,drivers,output):
    receipts=[p/'assessment.json' for p in [cut,boundary,drivers]];a,b,c=[json.loads(p.read_text()) for p in receipts]
    for r in [a,b,c]:verify(r['input_sha256']);verify(r['artifacts'])
    ext=next(Path(p) for p in a['input_sha256'] if p.endswith('/IntegerPLL_400MHz_KeeperFlatC.ext'));spice=ext.with_name('capacitance.spice');detail=boundary/'boundary.json';chain=drivers/'chains.json';cross=cut/'crossing_capacitors.json'
    pins={str(p):sha(p) for p in [*receipts,ext,spice,detail,chain,cross,Path(__file__).resolve(),Path(__file__).with_name('audit_keeper_flat_MOS_region_join.py'),Path(__file__).with_name('audit_keeper_DCO_driver_C_cut.py'),Path(__file__).with_name('native_spice_comments.py')]}
    aliases=Aliases()
    for line in ext.open():
        if line.startswith('equiv '):
            f=shlex.split(line);aliases.union(f[1],f[2])
    selected=set(json.loads(detail.read_text())['selected_primitives'])|set(json.loads(chain.read_text())['retained_MOS_cards']);nodes=set()
    for line in spice.open():
        f=strip_floating_annotation(line).split()
        if f and f[0] in selected:
            j=next((i for i,t in enumerate(f) if '=' in t),len(f))-1;nodes.update(aliases.find(n) for n in f[1:j])
    groups=defaultdict(list);total=F(0);exterior=set();labels=defaultdict(Counter)
    for row in json.loads(cross.read_text()):
        if row['kind']!='away_from_RTL_control_port':continue
        x,y=aliases.find(row['node1']),aliases.find(row['node2'])
        if (x in nodes)==(y in nodes):raise ValueError('not an actual crossing')
        inside,outside=(x,y) if x in nodes else (y,x);literal=row['node1'] if x in nodes else row['node2'];labels[inside][literal]+=1;exterior.add(outside);groups[inside].append(row);total+=capacitance(row['value'])
    records=[]
    for node,rows in groups.items():
        value=sum((capacitance(r['value']) for r in rows),F(0));records.append(dict(canonical_node=node,native_labels=dict(labels[node]),C_card_count=len(rows),total_capacitance_F_exact=str(value),total_capacitance_fF=float(value*10**15),maximum_charge_for_1p8V_exterior_excursion_C=float(value*F(18,10))))
    records.sort(key=lambda r:r['total_capacitance_fF'],reverse=True)
    if sum(r['C_card_count'] for r in records)!=a['C_card_counts']['away_from_RTL_control_port']:raise ValueError('same residual inventory required')
    verify(pins);output.mkdir(parents=True,exist_ok=False)
    save(output/'assessment.json',dict(input_sha256=pins,residual_non_control_C_card_count=sum(map(len,groups.values())),selected_node_count=len(groups),exterior_node_count=len(exterior),total_capacitance_F_exact=str(total),records=records,charge_excursion_assumption_V=1.8,charge_sum_is_frequency_or_phase_error_bound=False,exterior_nodes_clamped=False,circuit_partitioned=False,boundary_loading_qualified=False,model_qualified=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['cut','boundary','drivers','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['cut','boundary','drivers','output']))
