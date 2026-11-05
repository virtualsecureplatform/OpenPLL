#!/usr/bin/env python3
"""Check completed global field IDs under the original compilation deadline."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import time
from common import ROOT,save,sha
from compiled_charge import execute
from parallel_hash import sha_prefetch
from resources import identity,lease


def run(a):
    root,out=a.compiled.resolve(),a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    owner=json.loads((root/'owner.json').read_text());deadline=owner['deadline_uptime']
    save(out/'owner.json',dict(original_owner=str(root/'owner.json'),original_deadline_uptime=deadline,
         total_budget_restarted=False,compilation_repeated=False))
    while not (root/'assessment.json').exists():
        if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('original compilation deadline')
        if identity(owner['pid'])!=owner['birth']:raise ValueError('original compiler terminal without completed receipt')
        save(out/'status.json',dict(state='waiting_for_original_compilation_receipt',release_qualified=False))
        time.sleep(5)
    receipt=root/'assessment.json';r=json.loads(receipt.read_text())
    coverage=a.coverage.resolve()/'assessment.json';c=json.loads(coverage.read_text())
    if not r['all_ranges_compiled'] or not c['full_native_kernel_event_owner_range_coverage_verified']:
        raise ValueError('complete original compilation/coverage required')
    if c['input_sha256'].get(str(root/'input_manifest.json'))!=sha(root/'input_manifest.json'):
        raise ValueError('coverage uses different original compilation')
    paths=[receipt,coverage,a.binary.resolve(),root/'fields.json',root/'operators_manifest.json',
           Path(__file__).resolve(),ROOT/'tools/charge_compiler/audit_field_maps.cpp',ROOT/'tools/charge_compiler/json.hpp']
    expected=dict(r['artifacts'])
    for i in range(owner['workers']):
        proof=root/f'worker_{i}/assessment.json';p=json.loads(proof.read_text())
        if c['input_sha256'].get(str(proof))!=sha(proof):raise ValueError('completed shard changed since range audit')
        field=root/f'worker_{i}/fields.json';mapping=root/f'worker_{i}_field_map.json'
        paths.extend((proof,field,mapping));expected[str(field)]=p['artifacts'][str(field)]
    with lease(4,12,deadline):
        save(out/'status.json',dict(state='verifying_completed_field_artifact_hashes',release_qualified=False))
        with ThreadPoolExecutor(max_workers=4) as pool:
            hashes=list(pool.map(lambda p:sha_prefetch(p,readers=2,deadline=deadline),paths))
        pins=dict(zip(map(str,paths),hashes))
        for p,h in expected.items():
            if p in pins and pins[p]!=h:raise ValueError('completed field artifact differs: '+p)
        save(out/'input_manifest.json',dict(input_sha256=pins))
        save(out/'status.json',dict(state='independently_reconstructing_all_global_field_ids',release_qualified=False))
        execute([a.binary.resolve(),root,out/'native_result.json',deadline,owner['workers']],out/'native.log',deadline,8)
        result=json.loads((out/'native_result.json').read_text())
        for p,h in pins.items():
            if sha_prefetch(Path(p),readers=4,deadline=deadline)!=h:raise ValueError('field artifact changed during audit')
        save(out/'assessment.json',dict(**result,input_sha256=pins,
             artifacts={str(out/n):sha(out/n) for n in ('native_result.json','native.log','input_manifest.json')},
             original_compilation_deadline_preserved=True,compilation_repeated=False,
             operator_payloads_independently_rehashed=False,runtime_model_eligible=False))
        save(out/'status.json',dict(state='complete_global_field_map_audit_pass',release_qualified=False))
        print(json.dumps(result))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('compiled','coverage','binary','output'):p.add_argument('--'+name,required=True,type=Path)
    run(p.parse_args())
