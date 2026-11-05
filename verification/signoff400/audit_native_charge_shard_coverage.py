#!/usr/bin/env python3
"""Audit complete native range coverage; do not rerun extraction/compilation."""
import argparse
from collections import Counter
import json
from pathlib import Path
from common import save, sha


def footer(path):
    with path.open('rb') as f:
        f.seek(max(0,path.stat().st_size-4096));data=f.read()
    lines=data.splitlines()
    if not lines:raise ValueError('empty native trace')
    return lines[-1].decode().split()


def run(a):
    root,out=a.compiled.resolve(),a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    owner=json.loads((root/'owner.json').read_text());source=Path(owner['source'])
    manifest=json.loads((root/'input_manifest.json').read_text())
    native=json.loads((source/'assessment.json').read_text())
    spans=json.loads((root/'ranges.json').read_text());index=json.loads((root/'native_index.json').read_text())
    if len(spans)!=owner['workers'] or not spans:raise ValueError('complete configured shard set required')
    trace=source/'trace';pins={}
    for name in ('kernels.log','owners.log','surfaces.log','contributions.log','node_ids.json'):
        key=str(trace/name)
        if manifest['input_sha256'].get(key)!=native['artifacts'].get(key):
            raise ValueError('native/compiler consumed-hash lineage mismatch')
    k,o,s=[footer(trace/name) for name in ('kernels.log','owners.log','surfaces.log')]
    if k[0]!='END' or o[0]!='END' or s[0]!='END':raise ValueError('native terminal footer required')
    events,kernels=map(int,k[1:]);owned,owner_kernels=map(int,o[1:])
    if owner_kernels!=kernels or int(s[1])!=events or index['events']!=events:
        raise ValueError('independent native stream footer/index totals differ')
    if footer(trace/'contributions.log')!=['OPENPLL_END']:raise ValueError('incomplete contribution stream')
    expected_kernel,expected_event=1,0;counts=Counter()
    previous=None
    for i,span in enumerate(spans):
        if span['kernel_start']!=expected_kernel or span['event_start']!=expected_event:
            raise ValueError('native ID range gap/overlap')
        if span['kernel_end']<=span['kernel_start'] or span['event_end']<span['event_start']:
            raise ValueError('invalid native ID interval')
        for name in ('kernels','owners','surfaces','contributions'):
            lo,hi=span[name]
            if lo>hi or (previous is not None and previous[name][1]!=lo):
                raise ValueError('native byte range gap/overlap: '+name)
        receipt=root/f'worker_{i}/assessment.json';state=root/f'worker_{i}/status.json'
        r=json.loads(receipt.read_text());status=json.loads(state.read_text())
        if status['state']!='completed' or r['range_spec']!=span:raise ValueError('incomplete/mismatched shard')
        c=r['counts']
        if c['kernels']!=span['kernel_end']-span['kernel_start'] or c['events']!=span['event_end']-span['event_start']:
            raise ValueError('shard actual count differs from consumed native interval')
        if c['operators']!=sum(c.get('operator_'+kind,0) for kind in ('A','L','F')):
            raise ValueError('operator-kind accounting mismatch')
        if any(not isinstance(v,int) or v<0 for v in c.values()):raise ValueError('invalid counter')
        counts.update(c);expected_kernel=span['kernel_end'];expected_event=span['event_end'];previous=span
        pins[str(receipt)]=sha(receipt);pins[str(state)]=sha(state)
    if (expected_kernel,expected_event)!=(kernels+1,events) or counts['owned_pair_kernels']!=owned:
        raise ValueError('native full-layout total coverage mismatch')
    for name in ('owner.json','input_manifest.json','ranges.json','native_index.json'):
        p=root/name;pins[str(p)]=sha(p)
    pins[str(source/'assessment.json')]=sha(source/'assessment.json');pins[str(Path(__file__).resolve())]=sha(Path(__file__))
    save(out/'assessment.json',dict(input_sha256=pins,completed_shards=len(spans),counts=dict(counts),
        full_native_kernel_event_owner_range_coverage_verified=True,
        all_four_native_byte_stream_ranges_contiguous=True,native_footer_counts=dict(kernels=kernels,events=events,owned_pair_kernels=owned),
        consumed_hash_manifests_match=True,operator_payloads_independently_rehashed=False,
        merged_global_field_maps_checked=False,physical_RC_qualified=False,runtime_model_eligible=False,release_qualified=False))
    print(json.dumps(dict(shards=len(spans),kernels=kernels,events=events,owned_pair_kernels=owned,operators=counts['operators'])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('compiled','output'):p.add_argument('--'+name,required=True,type=Path)
    run(p.parse_args())
