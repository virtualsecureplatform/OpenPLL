#!/usr/bin/env python3
"""Build typed support candidates from audited C fields and final R snapshots."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import time
from common import ROOT,save,sha
from compiled_charge import execute
from parallel_hash import sha_prefetch
from resources import lease


def run(a):
    compiled,catalog,field_audit,catalog_audit,out=[p.resolve() for p in
        (a.compiled,a.catalog,a.field_audit,a.catalog_audit,a.output)]
    out.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    cr,rr,fr,ar=[p/'assessment.json' for p in (compiled,catalog,field_audit,catalog_audit)]
    c,r,f,v=[json.loads(p.read_text()) for p in (cr,rr,fr,ar)]
    if not f['all_field_maps_independently_reconstructed'] or f['input_sha256'].get(str(cr))!=sha(cr):
        raise ValueError('matching complete global field audit required')
    if not v['all_source_rows_independently_partitioned'] or v['input_sha256'].get(str(rr))!=sha(rr):
        raise ValueError('matching complete final R-catalog audit required')
    native=Path(json.loads((compiled/'owner.json').read_text())['source'])/'assessment.json'
    n=json.loads(native.read_text())
    if not n['native_C_and_device_cards_unchanged'] or not n['original_floating_nodes_preserved']:
        raise ValueError('native C/device and floating-identity proof required')
    if c['input_sha256'].get(str(native))!=sha(native):raise ValueError('compiled native receipt changed')
    all_catalog=Path(r['source_catalog'])/'assessment.json';all_r=json.loads(all_catalog.read_text())
    domains=[p for p in all_r['input_sha256'] if p.endswith('/domain/assessment.json')]
    if len(domains)!=1 or n['input_sha256'].get(domains[0])!=all_r['input_sha256'][domains[0]]:
        raise ValueError('C and R do not share the exact native layout/domain receipt')
    fields=compiled/'fields.json';metadata=compiled/'trace_metadata.json';tiles=catalog/'native/tile_catalog.jsonl'
    shard=compiled/'worker_0/assessment.json';shard_proof=json.loads(shard.read_text())
    paths=[cr,rr,fr,ar,native,all_catalog,Path(domains[0]),shard,fields,metadata,tiles,a.binary.resolve(),
           ROOT/'tools/native_rc_coverage/map_charge_fields_to_R.cpp',ROOT/'tools/charge_compiler/json.hpp',
           Path(__file__).resolve(),Path(__file__).with_name('parallel_hash.py'),Path(__file__).with_name('resources.py')]
    with lease(8,12,deadline):
        save(out/'status.json',dict(state='verifying_common_native_C_R_field_lineage',release_qualified=False))
        with ThreadPoolExecutor(max_workers=4) as pool:hashes=list(pool.map(lambda p:sha_prefetch(p,readers=2,deadline=deadline),paths))
        pins=dict(zip(map(str,paths),hashes))
        if (pins[str(fields)]!=c['artifacts'][str(fields)] or pins[str(fields)]!=f['input_sha256'][str(fields)] or
            pins[str(metadata)]!=shard_proof['input_sha256'][str(metadata)] or
            pins[str(tiles)]!=r['artifacts'][str(tiles)] or pins[str(tiles)]!=v['input_sha256'][str(tiles)]):
            raise ValueError('audited C/R source bytes changed')
        cfg=out/'config.json';save(cfg,dict(fields=str(fields),metadata=str(metadata),catalog=str(tiles),output=str(out/'native'),threads=8,deadline_uptime=deadline))
        save(out/'status.json',dict(state='mapping_all_charge_fields_to_typed_R_candidates',release_qualified=False))
        execute([a.binary.resolve(),cfg],out/'native.log',deadline,8)
        result=json.loads((out/'native/summary.json').read_text())
        if result['global_fields']!=f['global_fields'] or result['native_R_tiles']!=r['selected_rows']:
            raise ValueError('full C/R field/tile accounting mismatch')
        for p,h in pins.items():
            if sha_prefetch(Path(p),readers=4,deadline=deadline)!=h:raise ValueError('C/R input changed during mapping')
        artifacts={str(p):sha_prefetch(p,deadline=deadline) for p in
            (cfg,out/'native/summary.json',out/'native/R_tile_bundles.jsonl',out/'native/field_domains.jsonl')}
        save(out/'assessment.json',dict(**result,input_sha256=pins,artifacts=artifacts,
            common_native_layout_domain_receipt=domains[0],source_compiled=str(compiled),source_catalog=str(catalog),
            independent_map_audit_complete=False,unextracted_conductors_not_assumed_floating=True))
        save(out/'status.json',dict(state='typed_C_R_candidate_map_complete_pending_independent_audit',release_qualified=False))
        print(json.dumps(result))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('compiled','catalog','field-audit','catalog-audit','binary','output'):
        p.add_argument('--'+name,required=True,type=Path)
    run(p.parse_args())
