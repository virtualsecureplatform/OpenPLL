#!/usr/bin/env python3
"""Reconstruct every typed C/R association using independent stdlib parsing."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import time
from common import save,sha
from resources import lease


def run(a):
    root,out=a.mapping.resolve(),a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    receipt=root/'assessment.json';r=json.loads(receipt.read_text())
    compiled=Path(r['source_compiled']);catalog=Path(r['source_catalog'])
    fields=compiled/'fields.json';metadata=compiled/'trace_metadata.json';tiles=catalog/'native/tile_catalog.jsonl'
    bundle_path=root/'native/R_tile_bundles.jsonl';map_path=root/'native/field_domains.jsonl'
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    with lease(2,12,deadline):
        meta=json.loads(metadata.read_text());residues={}
        for plane,raw,effective in meta['residues']:
            key=(plane,raw)
            if key in residues and residues[key]!=effective:raise ValueError('conflicting native residue')
            residues[key]=effective
        expected={};conductors=set();tile_hash=hashlib.sha256();row_number=0
        with tiles.open('rb') as stream:
            while True:
                offset=stream.tell();raw=stream.readline()
                if not raw:break
                tile_hash.update(raw);row_number+=1;t=json.loads(raw)
                if meta['types'][t['raw_type_id']]!=t['raw_material']:raise ValueError('raw type namespace mismatch')
                plane=t['native_working_plane_id'];raw_type=int(t['raw_type_id']);effective=residues.get((plane,raw_type),raw_type)
                key=(t['original_conductor'],meta['planes'][str(plane)],meta['types'][str(effective)])
                expected.setdefault(key,[]).append([offset,row_number,t['native_group_id'],t['tile_serial'],raw_type,effective])
                conductors.add(t['original_conductor'])
        if tile_hash.hexdigest()!=r['input_sha256'][str(tiles)]:raise ValueError('R catalog changed')
        lookup={};bundle_hash=hashlib.sha256()
        with bundle_path.open('rb') as stream:
            for i,(key,references) in enumerate(expected.items()):
                raw=stream.readline();bundle_hash.update(raw);bundle=json.loads(raw)
                if bundle!={'bundle_id':i,'field_key':list(key),'tile_references':references}:
                    raise ValueError('bundle/source offset or native identity differs')
                lookup[key]=(i,len(references))
            if stream.read(1):raise ValueError('extra native R bundles')
        del expected
        raw=fields.read_bytes();field_hash=hashlib.sha256(raw).hexdigest();definitions=json.loads(raw);del raw
        if field_hash!=r['input_sha256'][str(fields)]:raise ValueError('C field table changed')
        counts=Counter({name:0 for name in ('explicit_reference','exact_native_R_tile_candidates','native_R_conductor_material_unmatched','no_native_R_snapshot_for_conductor','unlocated_native_field')});used=set();matched_tiles=0;map_hash=hashlib.sha256()
        with map_path.open('rb') as stream:
            for i,field in enumerate(definitions):
                if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('C/R audit deadline')
                key=tuple(field);row={'field_id':i,'field_key':field,'spatial_projection_qualified':False}
                if i==0:
                    if field!=['@SUBSTRATE_REFERENCE','reference','reference']:raise ValueError('reference identity changed')
                    state='explicit_reference'
                elif field[1:]==['arithmetic','unlocated']:state='unlocated_native_field'
                elif key in lookup:
                    state='exact_native_R_tile_candidates';bundle,n=lookup[key]
                    if bundle in used:raise ValueError('duplicate global C field uses native bundle')
                    used.add(bundle);matched_tiles+=n;row.update(R_tile_bundle_id=bundle,candidate_tiles=n)
                elif field[0] in conductors:state='native_R_conductor_material_unmatched'
                else:state='no_native_R_snapshot_for_conductor'
                row['support_state']=state;counts[state]+=1
                raw=stream.readline();map_hash.update(raw)
                if json.loads(raw)!=row:raise ValueError('typed C/R association differs at field '+str(i))
            if stream.read(1):raise ValueError('extra field associations')
        if (dict(counts)!=r['field_support_states'] or len(definitions)!=r['global_fields'] or
            row_number!=r['native_R_tiles'] or len(lookup)!=r['R_tile_bundles'] or matched_tiles!=r['matched_R_tile_candidates']):
            raise ValueError('C/R aggregate accounting differs')
        if bundle_hash.hexdigest()!=r['artifacts'][str(bundle_path)] or map_hash.hexdigest()!=r['artifacts'][str(map_path)]:
            raise ValueError('complete C/R map artifact hashes differ')
        pins={str(p):sha(p) for p in (receipt,metadata,Path(__file__).resolve(),Path(__file__).with_name('common.py'),Path(__file__).with_name('resources.py'))}
        pins.update({str(tiles):tile_hash.hexdigest(),str(fields):field_hash,str(bundle_path):bundle_hash.hexdigest(),str(map_path):map_hash.hexdigest()})
        save(out/'assessment.json',dict(input_sha256=pins,all_field_associations_independently_checked=True,
            all_R_tile_bundle_references_independently_checked=True,global_fields=len(definitions),native_R_tiles=row_number,
            field_support_states=dict(counts),R_tile_bundles=len(lookup),R_bundles_without_C_fields=len(lookup)-len(used),
            matched_R_tile_candidates=matched_tiles,spatial_projection_qualified=False,
            full_C_energy_matrix_assembled=False,physical_RC_qualified=False,runtime_model_eligible=False,release_qualified=False))
        print(json.dumps(dict(status='pass',global_fields=len(definitions),native_R_tiles=row_number,field_support_states=dict(counts))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('mapping','output'):p.add_argument('--'+name,required=True,type=Path)
    run(p.parse_args())
