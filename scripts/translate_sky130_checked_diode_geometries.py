#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Translate exactly the two independently checked physical diode geometries.

Accept only fresh Magic foundry-wrapper X instances with the documented native
area/perimeter encoding. Bind HD/HS electrical/noise evidence and the foundry
model before emitting explicit fixed-temperature level1 geometry wrappers.
The caller must set the same global Xyce temperature. This is diode-model
compatibility support; assembled PLL/model/timing qualification is separate.
"""
import argparse
from collections import Counter
from decimal import Decimal,InvalidOperation
import hashlib
import json
from pathlib import Path
import re
from sky130_diode_translation_probe import MODEL_SHA256,translated_model

DEVICE='sky130_fd_pr__diode_pw2nd_05v5'
GEOMETRIES={
    (Decimal('4.347e11'),Decimal('2.64e6')):('hd',Decimal('.4347'),Decimal('2.64')),
    (Decimal('6.417e11'),Decimal('3.24e6')):('hs',Decimal('.6417'),Decimal('3.24'))}
PREFIX='openpll_pw2nd_checked_'


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def translate(text):
    if re.search(r'(?im)^\s*\.end\s*$',text) or PREFIX in text or 'openpll_pw2nd_candidate' in text:
        raise ValueError('expected a fresh extracted include')
    if re.search(r'(?im)^\s*\.options?\b[^\n]*\bscale\s*=',text):
        raise ValueError('global scale conflicts with explicit checked diode geometry')
    lines=[];counts=Counter()
    for line in text.splitlines():
        if line.lstrip().startswith('*') or DEVICE not in line.lower():lines.append(line);continue
        f=line.split()
        if len(f)!=6 or not f[0].lower().startswith('x') or f[3].lower()!=DEVICE:
            raise ValueError('unsupported diode statement or continuation')
        params={}
        for token in f[4:]:
            if '=' not in token:raise ValueError('invalid diode parameter')
            key,value=token.lower().split('=',1)
            if key in params:raise ValueError('duplicate diode parameter')
            try:params[key]=Decimal(value)
            except InvalidOperation as error:raise ValueError('nonconstant diode geometry') from error
        if params.keys()!={'area','perim'}:raise ValueError('unsupported diode parameters')
        key=(params['area'],params['perim'])
        if key not in GEOMETRIES:raise ValueError('diode geometry outside checked scope')
        name,area,perimeter=GEOMETRIES[key]
        lines.append(' '.join(f[:3]+[PREFIX+name]));counts[name]+=1
    if not counts:raise ValueError('no checked diode instances')
    return '\n'.join(lines)+'\n',dict(counts)


def qualification(hd_path,hs_path,electrical_path,pdk):
    hd=json.loads(hd_path.read_text());hs=json.loads(hs_path.read_text())
    if not all(q.get('model_equivalence_screen_passed') is True for q in [hd,hs]):raise ValueError('comparison evidence has not passed')
    if '.4347' not in hd['scope'] or '2.64' not in hd['scope']:raise ValueError('HD geometry scope mismatch')
    if hs['effective_geometry']!={'area_um2':'.6417','perimeter_um':'3.24'}:raise ValueError('HS geometry scope mismatch')
    if hs['electrical_cases']!=15 or hs['noise_bias_cases']!=75 or hs['required_native_analyses']!=360:
        raise ValueError('incomplete HS comparison coverage')
    expected_corners={'tt','ff','ss','sf','fs'};expected_temperatures={-40,27,125}
    for q in [hd,hs]:
        if set(q['corners'])!=expected_corners or set(q['temperatures_c'])!=expected_temperatures:
            raise ValueError('PVT scope mismatch')
    if str(electrical_path.resolve()) not in hd['evidence_sha256']:raise ValueError('HD electrical parameters lack qualification binding')
    files={}
    def add(mapping):
        for path,value in mapping.items():
            if path in files and files[path]!=value:raise ValueError('conflicting evidence hashes')
            files[path]=value
    add(hd['evidence_sha256']);add(hs['input_sha256']);add(hs['artifacts'])
    # Check the explicit HS plan and native receipt too, including raw outputs.
    plan_path=next(Path(p) for p in hs['input_sha256'] if p.endswith('/plan.json'))
    native_path=next(Path(p) for p in hs['input_sha256'] if p.endswith('/native_completion.json'))
    plan=json.loads(plan_path.read_text());native=json.loads(native_path.read_text())
    if native.get('all_native_analyses_completed') is not True or len(native['results'])!=360 or any(r['exit_code'] for r in native['results']):
        raise ValueError('HS native analyses incomplete')
    add(native['input_sha256']);add(native['artifacts']);add(plan['prepared_deck_sha256'])
    for path,value in files.items():
        if digest(path)!=value:raise ValueError('qualification evidence changed: '+path)
    model=pdk/'libs.ref/sky130_fd_pr/spice/sky130_fd_pr__diode_pw2nd_05v5.model.spice'
    if digest(model)!=MODEL_SHA256:raise ValueError('foundry diode model changed')
    return json.loads(electrical_path.read_text())['corner_parameters'],files,model


def render(text,temperature,parameters):
    translated,counts=translate(text)
    translated+='\n* Checked diode compatibility only; physical PLL qualification remains separate.\n'
    translated+=translated_model(temperature,*parameters)
    for name in sorted(counts):
        _,area,perimeter=next(v for v in GEOMETRIES.values() if v[0]==name)
        translated+=f'.subckt {PREFIX}{name} N P\nD0 N P openpll_pw2nd_candidate area={area} pj={perimeter}\n.ends {PREFIX}{name}\n'
    return translated,counts


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['hd-qualification','hs-qualification','electrical','pdk','input','output']:p.add_argument('--'+name,required=True,type=Path)
    p.add_argument('--corner',required=True,choices=['tt','ff','ss','sf','fs'])
    p.add_argument('--temperature-c',required=True,type=int,choices=[-40,27,125])
    a=p.parse_args();report=a.output.with_suffix('.translation.json')
    if a.output.exists() or report.exists():p.error('use a fresh output path')
    parameters,evidence,model=qualification(a.hd_qualification,a.hs_qualification,a.electrical,a.pdk)
    translated,counts=render(a.input.read_text(),a.temperature_c,parameters[a.corner])
    a.output.parent.mkdir(exist_ok=True,parents=True);a.output.write_text(translated)
    record=dict(translated_instances=sum(counts.values()),translated_by_geometry=counts,corner=a.corner,
        required_global_Xyce_temperature_c=a.temperature_c,
        effective_geometries={name:dict(area_um2=str(area),perimeter_um=str(perimeter)) for name,area,perimeter in GEOMETRIES.values() if name in counts},
        qualification_evidence_sha256=evidence,input_sha256=digest(a.input),output_sha256=digest(a.output),
        HD_qualification_sha256=digest(a.hd_qualification),HS_qualification_sha256=digest(a.hs_qualification),
        foundry_model_sha256=digest(model),full_model_qualified=False,PLL_release_qualified=False)
    report.write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(dict(translated_by_geometry=counts,PLL_release_qualified=False)))


if __name__=='__main__':main()
