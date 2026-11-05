#!/usr/bin/env python3
"""Prove unlocated field IDs belong solely to native output-clamp bookkeeping."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
from common import ROOT,save,sha
from compiled_charge import execute
from parallel_hash import sha_prefetch
from resources import lease
sys.path.insert(0,str(ROOT/'verification/timing400'))
from parallel_C_trace_ranges import find_record


def kernel_offset(path,target):
    lo,hi=0,path.stat().st_size
    while hi-lo>1024*1024:
        mid=(lo+hi)//2;offset,row=find_record(path,mid,b'KERNEL ')
        if row is not None and int(row.split()[1])<target:lo=offset+len(row.encode())+1
        else:hi=mid
    offset,row=find_record(path,lo,b'KERNEL ')
    while row is not None and int(row.split()[1])<target:
        offset,row=find_record(path,offset+len(row.encode())+1,b'KERNEL ')
    if row is None or int(row.split()[1])!=target:raise ValueError('rounding kernel boundary missing')
    return offset


def run(a):
    compiled,out=a.compiled.resolve(),a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    receipt=compiled/'assessment.json';c=json.loads(receipt.read_text())
    owner=json.loads((compiled/'owner.json').read_text());source=Path(owner['source']);trace=source/'trace'
    field_path=compiled/'fields.json';surfaces=trace/'surfaces.log';kernels=trace/'kernels.log'
    mapping=a.mapping.resolve()/'assessment.json';m=json.loads(mapping.read_text())
    map_audit=a.map_audit.resolve()/'assessment.json';v=json.loads(map_audit.read_text())
    if not v['all_field_associations_independently_checked'] or v['input_sha256'].get(str(mapping))!=sha(mapping):
        raise ValueError('complete typed support-map audit required')
    if m['input_sha256'].get(str(receipt))!=sha(receipt):raise ValueError('support map uses different C compilation')
    build=ROOT/'build/timing400/release_001/magic_C_owner_trace_build_001/assessment.json'
    b=json.loads(build.read_text());native=json.loads((source/'assessment.json').read_text())
    legacy=ROOT/'build/timing400/magic_C_owner_source_001/extract/ExtBasic.c'
    if b['input_sha256'].get(str(legacy))!=sha(legacy):raise ValueError('native rounding instrumentation source differs')
    shared=[p for p in b['artifacts'] if p.endswith('.so') and p in native['input_sha256']]
    if not shared or any(b['artifacts'][p]!=native['input_sha256'][p] for p in shared):
        raise ValueError('native traced library/build lineage differs')
    text=legacy.read_text();cpp=ROOT/'tools/charge_compiler/main_stream_ledger.cpp';cpp_text=cpp.read_text()
    if 'OpenPLLKernelBegin("ROUNDING", NULL, NULL, -1)' not in text or '"output_zero_clamp"' not in text:
        raise ValueError('native output-clamp context semantics differ')
    if 'if(x.kind=="ROUNDING"){require(!pair,"pair rounding");return out;}' not in cpp_text:
        raise ValueError('compiled rounding must emit no physical operator')
    count=m['field_support_states']['unlocated_native_field']
    first_kernel=c['counts']['kernels']-count+1
    with lease(8,12,deadline):
        save(out/'status.json',dict(state='verifying_full_unlocated_surface_event_support',release_qualified=False))
        paths=[receipt,mapping,map_audit,build,legacy,cpp,a.binary.resolve(),field_path,surfaces,
               source/'assessment.json',compiled/'input_manifest.json',Path(__file__).resolve(),
               ROOT/'tools/charge_compiler/classify_surface_locations.cpp',ROOT/'tools/charge_compiler/json.hpp',
               ROOT/'verification/timing400/parallel_C_trace_ranges.py']
        pins={str(p):sha_prefetch(p,deadline=deadline) for p in paths}
        original=json.loads((compiled/'input_manifest.json').read_text())['input_sha256']
        if pins[str(surfaces)]!=original[str(surfaces)] or pins[str(field_path)]!=c['artifacts'][str(field_path)] or pins[str(cpp)]!=original[str(cpp)]:
            raise ValueError('completed native C/field inputs changed')
        raw=field_path.read_bytes();fields=json.loads(raw)
        if hashlib.sha256(raw).hexdigest()!=pins[str(field_path)]:raise ValueError('field table changed')
        indices=[i for i,f in enumerate(fields) if f[1:]==['arithmetic','unlocated']]
        if len(indices)!=count or indices!=list(range(len(fields)-count,len(fields))):
            raise ValueError('unlocated fields are not exactly a terminal field-ID interval')
        execute([a.binary.resolve(),surfaces,out/'surface_locations.json',deadline,8],out/'native.log',deadline,4)
        locations=json.loads((out/'surface_locations.json').read_text())
        if locations['events']!=c['counts']['events'] or locations['unlocated_G_events']!=count:
            raise ValueError('surface/field unlocated accounting differs')
        offset=kernel_offset(kernels,first_kernel);kernel_id=first_kernel;event_id=locations['first_unlocated_event'];pending=False;ended=False;h=hashlib.sha256()
        with kernels.open('rb') as stream:
            stream.seek(offset)
            for raw in stream:
                h.update(raw);f=raw.decode().split()
                if ended:raise ValueError('data after terminal kernel footer')
                if f==['KERNEL',str(kernel_id),'ROUNDING','-1'] and not pending:pending=True
                elif f==['EVENT',str(event_id),'G',str(kernel_id),'NODE_ROUNDING'] and pending:
                    pending=False;kernel_id+=1;event_id+=1
                elif f==['END',str(c['counts']['events']),str(c['counts']['kernels'])] and not pending:ended=True
                else:raise ValueError('unlocated native suffix contains non-rounding or spatial records')
        if not ended or kernel_id!=c['counts']['kernels']+1 or event_id!=c['counts']['events']+1:
            raise ValueError('incomplete native rounding suffix')
        for p,value in pins.items():
            if sha_prefetch(Path(p),deadline=deadline)!=value:raise ValueError('rounding-classification input changed')
        save(out/'field_role_intervals.json',dict(format='half_open_global_field_id_intervals_v1',reference_field_id=0,
            physical_operator_field_id_interval=[0,len(fields)-count],arithmetic_bookkeeping_field_id_interval=[len(fields)-count,len(fields)],
            arithmetic_fields_emit_no_physical_operators=True,physical_voltage_state_basis_constructed=False,release_qualified=False))
        save(out/'assessment.json',dict(input_sha256=pins,
            artifacts={str(out/n):sha(out/n) for n in ('surface_locations.json','native.log','field_role_intervals.json')},
            rounding_only_fields=count,physical_operator_fields_including_reference=len(fields)-count,
            complete_surface_stream_checked=True,native_rounding_kernel_suffix_checked=True,
            native_kernel_suffix_byte_offset=offset,native_kernel_suffix_sha256=h.hexdigest(),
            retained_whole_kernel_sha256=original[str(kernels)],whole_kernel_payload_independently_rehashed=False,
            arithmetic_fields_emit_no_physical_operators=True,arithmetic_ledger_records_preserved=True,
            physical_RC_qualified=False,global_passivity_qualified=False,runtime_model_eligible=False,release_qualified=False))
        save(out/'status.json',dict(state='native_rounding_only_field_interval_verified',release_qualified=False))
        print(json.dumps(dict(rounding_only_fields=count,physical_operator_fields_including_reference=len(fields)-count)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('compiled','mapping','map-audit','binary','output'):p.add_argument('--'+name,required=True,type=Path)
    run(p.parse_args())
