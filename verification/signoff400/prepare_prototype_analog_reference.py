"""Isolate the matching analog hierarchy as a reference, never as completed PEX."""
import argparse
from collections import Counter
import json
from pathlib import Path
from common import save,sha,verify


def subcircuits(text):
    result={};name=None;lines=[]
    for line in text.splitlines(True):
        if line.lower().startswith('.subckt '):
            if name is not None:raise ValueError('nested subcircuit')
            name=line.split()[1];lines=[line]
        elif name is not None:
            lines.append(line)
            if line.lower().startswith('.ends'):
                if name in result:raise ValueError('duplicate subcircuit')
                result[name]=''.join(lines);name=None
    if name is not None:raise ValueError('unterminated subcircuit')
    return result


def closure(blocks,top):
    found=set();pending=[top];primitives=set()
    while pending:
        name=pending.pop()
        if name in found:continue
        if name not in blocks:raise ValueError('missing requested analog top')
        found.add(name)
        # Join continuation records before locating instance model tokens.
        records=[]
        for line in blocks[name].splitlines():
            if line.startswith('+'):
                if not records:raise ValueError('orphan continuation')
                records[-1]+=' '+line[1:]
            else:records.append(line)
        for line in records:
            if not line or line[0].lower()!='x':continue
            positional=[]
            for token in line.split()[1:]:
                if '=' in token:break
                positional.append(token)
            if not positional:raise ValueError('subcircuit instance without model')
            model=positional[-1]
            if model in blocks:pending.append(model)
            elif model.startswith('sky130_fd_pr__'):primitives.add(model)
            else:raise ValueError('unresolved hierarchical model: '+model)
    return found,primitives


def run(layout,output):
    output.mkdir(parents=True,exist_ok=False);receipt=layout/'assessment.json';a=json.loads(receipt.read_text())
    source=layout/'assembly.spice';gds=layout/'assembly.gds'
    paths=[receipt,source,gds,Path(__file__).resolve()];pins={str(p):sha(p) for p in paths}
    if not a.get('assembled_lvs_pass') or any(a['artifacts'].get(str(p))!=pins[str(p)] for p in (source,gds)):
        raise ValueError('matching checked assembly source and GDS required')
    blocks=subcircuits(source.read_text());tops=[n for n in blocks if n.startswith('IntegerPLL_DCO_') or n=='IntegerPLL_BBPD']
    if len(tops)!=2:raise ValueError('unique DCO and detector hierarchy required')
    results=[];artifacts={}
    for top in sorted(tops):
        names,models=closure(blocks,top);target=output/(top+'.spice')
        target.write_text('* Reference hierarchy only: final interconnect/loading PEX is not included.\n'+''.join(blocks[n] for n in sorted(names)))
        artifacts[str(target)]=sha(target)
        counts=Counter(line[0].upper() for n in names for line in blocks[n].splitlines() if line and line[0].upper() in 'XRCMD')
        results.append(dict(top=top,file=str(target),subcircuits=len(names),primitive_models=sorted(models),record_counts=dict(counts)))
    verify(pins);save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,analog_hierarchies=results,
        matching_layout_reference_hierarchies_isolated=True,final_loading_parasitics_complete=False,
        device_geometry_and_known_model_issues_reviewed=False,validated_for_prototype=False,diagnostic=True,
        release_ready=False,production_qualified=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('layout','output'):p.add_argument('--'+name,required=True,type=Path)
    a=p.parse_args();run(a.layout.resolve(),a.output.resolve())
