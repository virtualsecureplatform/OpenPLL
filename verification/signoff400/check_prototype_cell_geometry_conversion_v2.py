"""Check native primitive geometry conversion in every extracted standard-cell master."""
import argparse
from collections import Counter
from fractions import Fraction as F
import json
from pathlib import Path
import shlex
from common import ROOT,save,sha,verify
from prepare_prototype_analog_reference import subcircuits


def extracted_features(text,grid):
    result=Counter()
    for line in text.splitlines():
        f=shlex.split(line)
        if not f or f[0]!='device':continue
        if f[1] not in ('msubckt','rsubckt'):raise ValueError('unreviewed native device record '+f[1])
        if f[1]=='rsubckt' and f[2]!='sky130_fd_pr__res_generic_po':raise ValueError('unreviewed resistor model')
        model=f[2];p=dict(t.split('=',1) for t in f if '=' in t)
        if 'nfet' in model or 'pfet' in model or model=='sky130_fd_pr__res_generic_po':
            feature=(model,'l_w',str(F(p['l'])*grid),str(F(p['w'])*grid))
        elif model=='sky130_fd_pr__diode_pw2nd_05v5':
            # PDK generic-diode instance parameters use the scaled model convention.
            feature=(model,'area_perim',str(F(p['a'])*grid*grid*10**12),str(F(p['p'])*grid*10**6))
        else:raise ValueError('unreviewed extracted primitive geometry '+model)
        result[feature]+=1
    return result


def spice_features(block):
    rows=[]
    for line in block.splitlines():
        if line.startswith('+'):rows[-1]+=' '+line[1:]
        elif line.strip():rows.append(line)
    result=Counter()
    for row in rows:
        if not row.startswith('X'):continue
        f=row.split();pos=[x for x in f[1:] if '=' not in x];model=pos[-1]
        p=dict(x.split('=',1) for x in f if '=' in x)
        if 'nfet' in model or 'pfet' in model or model=='sky130_fd_pr__res_generic_po':
            feature=(model,'l_w',str(F(p['l'])),str(F(p['w'])))
        elif model=='sky130_fd_pr__diode_pw2nd_05v5':
            feature=(model,'area_perim',str(F(p['area'])),str(F(p['perim'])))
        else:raise ValueError('unreviewed native primitive geometry '+model)
        if any(k in p for k in ('m','mult','nf')):raise ValueError('primitive multiplicity needs explicit geometry expansion')
        result[feature]+=1
    return result


def run(source,output):
    output.mkdir(parents=True,exist_ok=False)
    receipt=source/'native_assessment.json';r=json.loads(receipt.read_text())
    netlist=source/'IntegerPLL_400MHz_PrototypeTop/capacitance.spice'
    if r['artifacts'].get(str(netlist))!=sha(netlist):raise ValueError('assembled native model changed')
    grid_receipt=ROOT/'build/signoff400/prototype_v3_DCO_instance_grid_validation_001/assessment.json'
    g=json.loads(grid_receipt.read_text())
    if not g.get('exact_primitive_length_width_grid_match'):raise ValueError('independent grid control required')
    grid=F(g['magic_grid_um']);blocks=subcircuits(netlist.read_text());paths=[receipt,netlist,grid_receipt,Path(__file__).resolve()];results=[]
    for name,block in sorted(blocks.items()):
        if not name.startswith('sky130_fd_sc_'):continue
        ext=netlist.parent/(name+'.ext');paths.append(ext)
        if r['artifacts'].get(str(ext))!=sha(ext):raise ValueError('extracted geometry not pinned')
        a=extracted_features(ext.read_text(),grid);b=spice_features(block)
        results.append(dict(master=name,raw_extracted_primitives=a.total(),native_primitives=b.total(),
            exact_geometry_feature_multisets_match=a==b,
            missing=[dict(feature=list(k),count=v) for k,v in (a-b).items()],
            added=[dict(feature=list(k),count=v) for k,v in (b-a).items()]))
    if not results:raise ValueError('no standard-cell geometry controls')
    pins={str(p):sha(p) for p in paths};detail=output/'masters.json';save(detail,results);verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},
        magic_grid_um=str(grid),standard_cell_masters=len(results),
        all_primitive_geometry_features_match=all(x['exact_geometry_feature_multisets_match'] for x in results),
        source_drain_area_perimeter_conversion_reviewed=False,model_physics_qualified=False,
        validated_for_prototype=False,release_ready=False))
    print('Masters:',len(results),'matching:',sum(x['exact_geometry_feature_multisets_match'] for x in results))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run(a.source.resolve(),a.output.resolve())
