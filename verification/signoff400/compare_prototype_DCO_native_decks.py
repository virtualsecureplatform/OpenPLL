"""Prove DCO deck identity except explicit solver/tolerance controls; no numerical qualification."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from common_v3 import save,sha,verify


def normalize(text):
    lines=[];controls={};klu=False
    for line in text.splitlines():
        fields=line.split()
        if not fields or fields[0].startswith('*'):continue
        if fields[0].lower() in ('.option','.options'):
            retained=[]
            for token in fields[1:]:
                if token.lower()=='klu':
                    if klu:raise ValueError('duplicate KLU selection')
                    klu=True;continue
                key,sep,value=token.partition('=')
                if key.lower() in ('reltol','abstol'):
                    if not sep or key.lower() in controls:raise ValueError('missing/duplicate numerical option')
                    number=float(value)
                    if not math.isfinite(number) or number<=0:raise ValueError('invalid numerical tolerance')
                    controls[key.lower()]=number;retained.append(key.lower()+'=<numerical>')
                else:retained.append(token)
            if retained:lines.append('.option '+' '.join(retained))
        else:lines.append(line)
    if set(controls)!={'reltol','abstol'}:raise ValueError('explicit RELTOL and ABSTOL required')
    return '\n'.join(lines)+'\n',dict(**controls,klu_selected=klu)


def compare(left,right):
    a,ac=normalize(left);b,bc=normalize(right)
    if a!=b:raise ValueError('DCO physical deck or undeclared numerical settings differ')
    return dict(normalized_deck_sha256=hashlib.sha256(a.encode()).hexdigest(),baseline_controls=ac,alternative_controls=bc,
        all_other_native_deck_records_identical=True,numerical_convergence_qualified=False),a


def run(baseline,alternative,output):
    output.mkdir(parents=True,exist_ok=False);pins={};decks=[]
    for directory in (baseline,alternative):
        manifest=directory/'input_manifest.json';m=json.loads(manifest.read_text());verify(m['input_sha256'])
        files=list((directory/'native').glob('dco_postlayout_*code_*.spice'))
        if len(files)!=1:raise ValueError('one generated DCO deck required')
        deck=files[0];pins.update({str(p):sha(p) for p in (manifest,deck)});decks.append(deck)
        pins.update(m['input_sha256'])
    pins[str(Path(__file__).resolve())]=sha(Path(__file__).resolve())
    result,normalized=compare(*(p.read_text() for p in decks))
    detail=output/'normalized.spice';detail.write_text(normalized);verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},comparison=result,
        waveform_results_compared=False,diagnostic=True,validated_for_prototype=False,release_ready=False))
    print('Physical decks identical except declared solver/RELTOL/ABSTOL controls')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('baseline','alternative','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(a.baseline.resolve(),a.alternative.resolve(),a.output.resolve())
