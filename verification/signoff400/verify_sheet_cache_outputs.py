#!/usr/bin/env python3
"""Verify all emitted cached/uncached matrix batches against pinned base cases."""
import argparse
import json
from pathlib import Path
import struct
from common import save,sha,verify

def validate_replicas(base,rows,copies=8):
    expected={r['id']:r for r in base}
    if len(expected)!=len(base) or len(rows)!=len(base)*copies:raise ValueError('matrix replica count differs')
    seen=set()
    for row in rows:
        name,separator,replica=row['id'].rpartition(':replica')
        if not separator or name not in expected or not replica.isdigit() or not 0<=int(replica)<copies or row['id'] in seen:raise ValueError('invalid or duplicate matrix replica identity')
        seen.add(row['id']);reference=expected[name]
        if row['nodes']!=reference['nodes'] or len(row['matrix'])!=len(reference['matrix']):raise ValueError('matrix identity or shape differs')
        for a,b in zip(row['matrix'],reference['matrix']):
            if a[:2]!=b[:2] or struct.pack('>d',float(a[2]))!=struct.pack('>d',float(b[2])):raise ValueError('matrix coefficient bits differ')
    return len(rows)
def read(path):return [json.loads(s) for s in Path(path).read_text().splitlines()]
def run(reference,candidate,output):
    reference,candidate,out=(Path(p).resolve() for p in (reference,candidate,output));out.mkdir(parents=True,exist_ok=False)
    refs=[];pins={};base_path=reference/'comparison/matrices.jsonl'
    for directory in (reference,candidate):
        p=directory/'assessment.json';proof=json.loads(p.read_text());verify(proof['input_sha256']);verify(proof['artifacts']);pins[str(p)]=sha(p);refs.append(proof)
    if len({r['shared_geometry_sha256'] for r in refs})!=1 or not all(r['selected_local_matrix_comparisons_passed'] for r in refs):raise ValueError('passing same-geometry matrix references required')
    pins[str(base_path)]=refs[0]['artifacts'][str(base_path)];candidate_base=candidate/'comparison/matrices.jsonl';pins[str(candidate_base)]=refs[1]['artifacts'][str(candidate_base)]
    if pins[str(base_path)]!=pins[str(candidate_base)]:raise ValueError('cached comparison bytes differ')
    base=read(base_path);count=0;identical=[]
    for threads in (1,4,8,16,32):
        left=reference/('threads_'+str(threads))/'matrices.jsonl';right=candidate/('threads_'+str(threads))/'matrices.jsonl'
        for p in (left,right):pins[str(p)]=sha(p);count+=validate_replicas(base,read(p))
        if pins[str(left)]!=pins[str(right)]:raise ValueError('cached/uncached thread batch bytes differ')
        identical.append(threads)
    pins[str(Path(__file__).resolve())]=sha(Path(__file__).resolve());verify(pins)
    result=dict(input_sha256=pins,base_matrix_cases=len(base),replica_matrix_records_checked=count,cached_and_uncached_literal_bytes_identical_at_threads=identical,all_replicas_match_base_numeric_bits=True,physical_domain_complete=False,runtime_model_eligible=False,release_qualified=False)
    save(out/'assessment.json',result);return result
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('reference','candidate','output'):p.add_argument('--'+n,required=True,type=Path)
    a=p.parse_args();r=run(a.reference,a.candidate,a.output);print(json.dumps({k:r[k] for k in ('base_matrix_cases','replica_matrix_records_checked')}))
