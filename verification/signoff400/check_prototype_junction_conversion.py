"""Check conventional MOS junction-attribute conversion against five-digit decimal rounding."""
import argparse
from collections import defaultdict
from fractions import Fraction as F
import json
from pathlib import Path
import shlex
from common import ROOT,save,sha,verify
from prepare_prototype_analog_reference import subcircuits


def tolerance(value):
    if not value:return F(0)
    value=abs(value);order=len(str(value.numerator))-len(str(value.denominator))
    power=lambda n:F(10**n) if n>=0 else F(1,10**(-n))
    if value<power(order):order-=1
    return power(order-4)/2


def compatible(a,b):
    return all(abs(x-y)<=tolerance(x) for x,y in zip(a,b))


def match(raw,native):
    if len(raw)!=len(native):return None
    edges={i:[j for j,b in enumerate(native) if compatible(a,b) or compatible(a,b[2:]+b[:2])] for i,a in enumerate(raw)}
    assigned={}
    def augment(i,seen):
        for j in edges[i]:
            if j in seen:continue
            seen.add(j)
            if j not in assigned or augment(assigned[j],seen):assigned[j]=i;return True
        return False
    for i in range(len(raw)):
        if not augment(i,set()):return None
    return assigned


def inventory(ext,spice,grid):
    raw=defaultdict(list);native=defaultdict(list)
    for line in ext.splitlines():
        f=shlex.split(line)
        if f[:2]!=['device','msubckt'] or not ('nfet' in f[2] or 'pfet' in f[2]):continue
        p=dict(t.split('=',1) for t in f if '=' in t);tail=f[-10:]
        a,ps=map(F,tail[6].split(','));d,pd=map(F,tail[9].split(','))
        raw[(f[2],F(p['l'])*grid,F(p['w'])*grid)].append((a*grid*grid,ps*grid,d*grid*grid,pd*grid))
    rows=[]
    for line in spice.splitlines():
        if line.startswith('+'):rows[-1]+=' '+line[1:]
        elif line.strip():rows.append(line)
    for line in rows:
        if not line.startswith('X'):continue
        f=line.split();pos=[t for t in f[1:] if '=' not in t];model=pos[-1]
        if not ('nfet' in model or 'pfet' in model):continue
        p=dict(t.split('=',1) for t in f if '=' in t)
        native[(model,F(p['l']),F(p['w']))].append(tuple(F(p[k]) for k in ('as','ps','ad','pd')))
    return raw,native


def run(source,output):
    output.mkdir(parents=True,exist_ok=False);receipt=source/'native_assessment.json';r=json.loads(receipt.read_text())
    netlist=source/'IntegerPLL_400MHz_PrototypeTop/capacitance.spice'
    gr=ROOT/'build/signoff400/prototype_v3_DCO_instance_grid_validation_001/assessment.json';grid=F(json.loads(gr.read_text())['magic_grid_um'])
    if r['artifacts'].get(str(netlist))!=sha(netlist):raise ValueError('assembled source changed')
    paths=[receipt,netlist,gr,Path(__file__).resolve()];results=[]
    for master,block in sorted(subcircuits(netlist.read_text()).items()):
        if not master.startswith('sky130_fd_sc_'):continue
        ext=netlist.parent/(master+'.ext');paths.append(ext)
        if r['artifacts'].get(str(ext))!=sha(ext):raise ValueError('extracted junction attributes changed')
        raw,native=inventory(ext.read_text(),block,grid);bad=[]
        for key in raw.keys()|native.keys():
            if match(raw[key],native[key]) is None:
                bad.append(dict(model=key[0],length_um=str(key[1]),width_um=str(key[2]),
                     extracted=[list(map(str,a)) for a in raw[key]],native=[list(map(str,a)) for a in native[key]]))
        results.append(dict(master=master,mos_primitives=sum(map(len,raw.values())),
             consistent_with_five_significant_digit_rounding=not bad,unmatched_groups=bad))
    detail=output/'masters.json';save(detail,results);pins={str(p):sha(p) for p in paths};verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},standard_cell_masters=len(results),
        all_junction_attributes_consistent_with_five_digit_rounding=all(x['consistent_with_five_significant_digit_rounding'] for x in results),
        comparison='One-to-one MOS geometry groups; source/drain exchange allowed; each area/perimeter within half of the fifth significant decimal unit of its extracted value.',
        independent_diffusion_polygon_geometry_proved=False,device_model_physics_qualified=False,
        validated_for_prototype=False,release_ready=False))
    print('Masters:',len(results),'junction conversion consistent:',sum(x['consistent_with_five_significant_digit_rounding'] for x in results))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run(a.source.resolve(),a.output.resolve())
