"""Trace native resistance-node ground capacitance to retained EXT coupling."""
import argparse,json,re
from fractions import Fraction as F
from pathlib import Path
from common_v3 import save,sha,verify

def run(pilot,contraction,output):
    receipts=[pilot/'assessment.json',contraction/'assessment.json']
    a,b=[json.loads(p.read_text()) for p in receipts]
    for record in [a,b]:
        verify(record['input_sha256'])
        verify(record.get('artifacts',{}))
    if not a['native_process_completed'] or b['input_sha256'].get(str(receipts[0]))!=sha(receipts[0]):
        raise ValueError('same normally completed resistance pilot required')
    ext=pilot/'IntegerPLL_400MHz_KeeperFlatC.ext';res=pilot/'IntegerPLL_400MHz_KeeperFlatC.res.ext'
    pins={str(p):sha(p) for p in [*receipts,ext,res,Path(__file__).resolve()]}
    parents={}
    def find(n):
        parents.setdefault(n,n)
        if parents[n]!=n:parents[n]=find(parents[n])
        return parents[n]
    for line in ext.open():
        if line.startswith('equiv '):
            n,m=re.findall(r'"([^\"]*)"',line)[:2];parents[find(n)]=find(m)
    root=find('PLLOUT');coupling=F(0);count=0
    for line in ext.open():
        if not line.startswith('cap '):continue
        match=re.fullmatch(r'cap "([^\"]*)" "([^\"]*)" (\S+)\s*',line)
        if not match:raise ValueError('unrecognized native coupling record')
        n,m,value=match.groups()
        if (find(n)==root)!=(find(m)==root):coupling+=F(value);count+=1
    values=[F(line.split()[3]) for line in res.open() if line.startswith('rnode ')]
    changes=b['C_pair_differences']
    if len(changes)!=1 or changes[0]['nodes']!=['pllout','vgnd']:
        raise ValueError('isolated PLLOUT ground-capacitance difference required')
    delta=F(changes[0]['contracted_F_exact'])-F(changes[0]['reference_F_exact'])
    verify(pins);output.mkdir(parents=True,exist_ok=False)
    save(output/'assessment.json',dict(input_sha256=pins,raw_coupling_branches=count,
        coupling_fF=float(coupling/1000),resistance_nodes=len(values),
        added_rnode_ground_C_fF=float(sum(values,F(0))/1000),exported_ground_C_delta_fF=float(delta*10**15),
        rnode_minus_coupling_fF=float((sum(values,F(0))-coupling)/1000),
        exact_equality=False,native_float_and_export_rounding_not_removed=True,
        spatial_capacitance_placement_qualified=False,model_qualified=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['pilot','contraction','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.pilot.resolve(),a.contraction.resolve(),a.output.resolve())
