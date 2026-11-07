"""Find exact one/two-node negative energy witnesses without modifying C."""
import argparse,json
from collections import defaultdict
from fractions import Fraction as F
from pathlib import Path
from common_v3 import save,sha,verify
from project_prototype_fixed_rail_C_v2 import project,RAILS,FIXED
from audit_hierarchical_capacitance import number


def witness(pairs):
    diagonal=defaultdict(F)
    for (a,b),c in pairs.items():diagonal[a]+=c;diagonal[b]+=c
    candidates=[]
    for n,d in diagonal.items():
        if n!=FIXED and d<0:candidates.append({n:F(1)})
    if not candidates:
        for (a,b),c in pairs.items():
            if FIXED in (a,b):continue
            da,db=diagonal[a],diagonal[b]
            if db>0 and da*db<c*c:candidates.append({a:F(1),b:c/db})
            elif da>0 and da*db<c*c:candidates.append({b:F(1),a:c/da})
            elif da==db==0 and c:candidates.append({a:F(1),b:F(1 if c>0 else -1)})
    for vector in candidates:
        energy=sum((c*(vector.get(a,F())-vector.get(b,F()))**2 for (a,b),c in pairs.items()),F())
        if energy>=0:raise ValueError('principal-minor candidate did not reproduce exact negative energy')
        return dict(indefiniteness_proved=True,voltage_vector={n:str(v)for n,v in vector.items()},exact_twice_energy_J=str(energy),all_omitted_voltages_zero=True)
    return dict(indefiniteness_proved=False,scope='one and two node principal minors only; no PSD certificate')


def run(source,output):
    receipt=source/'assessment.json';r=json.loads(receipt.read_text());verify(r['input_sha256']);verify(r['artifacts'])
    output.mkdir(parents=True,exist_ok=False);pins={str(receipt):sha(receipt),str(Path(__file__).resolve()):sha(Path(__file__))};results=[]
    for row in r['results']:
        model=source/(row['corner']+'_'+row['attachment']+'.spice')
        if r['artifacts'].get(str(model))!=sha(model):raise ValueError('model differs')
        pins[str(model)]=sha(model);pairs=defaultdict(F)
        for line in model.read_text().splitlines():
            f=line.split()
            if f and f[0].startswith('Cflat'):pairs[tuple(sorted(f[1:3]))]+=number(f[3])
        result=witness(project(pairs,set(RAILS)));results.append(dict(corner=row['corner'],attachment=row['attachment'],**result))
    verify(pins);save(output/'assessment.json',dict(input_sha256=pins,artifacts={},results=results,models_modified=False,passivity_certified=False,native_simulation_allowed=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args();run(a.source.resolve(),a.output.resolve())
