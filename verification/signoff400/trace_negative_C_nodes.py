"""Resolve every exact negative conservative diagonal to its original voltage fields."""
import argparse
from array import array
import json
import os
from pathlib import Path
import re
import struct
import sys
import time
from common import ROOT, save, sha, verify
from resources import identity, lease


def run(output):
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,
         cpu_slots=1,memory_GiB=1,automatic_identical_retry=False))
    base=ROOT/'build/signoff400';replay=base/'startup_timing_conservative_C_row_replay_001/assessment.json'
    replayed=json.loads(replay.read_text());certificate=base/'startup_timing_conservative_C_001/assessment.json'
    a=json.loads(certificate.read_text());manifest=Path(a['logical_operator_manifest']);op=json.loads(manifest.read_text())
    rows=Path(op['correction_certificate']['path']);transform=Path(op['voltage_namespace_receipt']['path'])
    t=json.loads(transform.read_text());mapping=base/'startup_timing_zero_R_voltage_map_002/voltage_map.bin'
    projection=base/'startup_timing_full_spatial_projection_002/assessment.json';p=json.loads(projection.read_text())
    geometry=json.loads((projection.parent/'config.json').read_text())['geometry']
    index=Path(geometry['R_index']);bundles=Path(geometry['R_bundles'])
    nodefile=Path('/tmp/openpll-spatial-charge-3g9ks0nr/native/R_nodes.jsonl')
    paths=[replay,certificate,manifest,rows,transform,mapping,projection,nodefile,index,bundles,Path(__file__).resolve()]
    try:
        with lease(1,1,deadline):
            pins={str(p):sha(p) for p in paths}
            if (pins[str(rows)]!=a['artifacts'][str(rows)] or pins[str(rows)]!=replayed['input_sha256'][str(rows)]
                    or pins[str(mapping)]!=t['input_sha256'][str(mapping)]
                    or pins[str(nodefile)]!=p['artifacts'][str(nodefile)]):raise ValueError('negative-node trace input changed')
            if any(pins[str(path)]!=p['input_sha256'][str(path)] for path in (index,bundles)):
                raise ValueError('R field/bundle source changed')
            save(output/'status.json',dict(state='locating_exact_negative_nodes',release_qualified=False))
            negatives={};count=0
            with rows.open() as stream:
                for line in stream:
                    count+=1
                    if count%10000==0 and time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('trace deadline')
                    # The pinned native certificate is compact canonical JSON, independently replayed in full.
                    if '"conservative_diagonal_integer":"-' in line:
                        row=json.loads(line);i=row['row'];assert int(row['conservative_diagonal_integer'])<0
                        negatives[i]=dict(row=i,energy_integer=row['conservative_diagonal_integer'],original_voltage_nodes=[])
            if count!=op['node_count'] or len(negatives)!=replayed['results']['negative_conservative_diagonals']:
                raise ValueError('negative-node/certificate coverage mismatch')
            if sys.byteorder!='little':raise ValueError('little-endian compacting map required')
            with mapping.open('rb') as stream:
                header=stream.read(24);original,constrained=struct.unpack('<QQ',header[8:])
                if header[:8]!=b'CNETDOF1' or constrained!=op['node_count']:raise ValueError('compacting map namespace differs')
                values=array('I');values.fromfile(stream,original)
                if stream.read(1):raise ValueError('compacting map trailing bytes')
            old_targets={}
            for old,new in enumerate(values):
                if new in negatives:old_targets[old]=new
            missing=set(old_targets);fields=set();groups=set()
            with nodefile.open() as stream:
                for line in stream:
                    node=int(line[1:line.index(',')])
                    if node not in missing:continue
                    actual,name=json.loads(line)
                    if actual!=node:raise ValueError('node namespace record differs')
                    match=re.fullmatch(r'(?:_rmesh_(?:axis_end_|sheet_)?|_zero_R_)(\d+)_.+',name)
                    if not match:raise ValueError('negative state needs another physical field resolver')
                    group=int(match[1]);groups.add(group)
                    negatives[old_targets[node]]['original_voltage_nodes'].append(dict(node=node,name=name,native_group=group))
                    missing.remove(node)
                    if not missing:break
            if missing:raise ValueError('negative voltage state not found in exact R namespace')
            raw=index.read_bytes()
            if raw[:8]!=b'RBSIDX01' or len(raw)!=16+16*geometry['global_fields']:
                raise ValueError('R field index format differs')
            bundle_field={}
            for field in range(1,geometry['global_fields']):
                start,_,bundle=struct.unpack_from('<QII',raw,16+16*field)
                if start!=2**64-1:
                    if bundle in bundle_field:raise ValueError('R bundle has multiple fields')
                    bundle_field[bundle]=field
            group_fields={group:set() for group in groups}
            with bundles.open() as stream:
                for line in stream:
                    row=json.loads(line);field=bundle_field[row['bundle_id']]
                    for reference in row['tile_references']:
                        group=int(reference[2])
                        if group in group_fields:group_fields[group].add(field)
            if any(not v for v in group_fields.values()):raise ValueError('native group lacks physical R fields')
            for row in negatives.values():
                for node in row['original_voltage_nodes']:
                    node['candidate_global_fields']=sorted(group_fields[node['native_group']])
                    fields.update(node['candidate_global_fields'])
            target=output/'targets.json'
            save(target,dict(schema_version=1,negative_nodes=list(negatives.values()),global_fields=sorted(fields),
                 energy_binary_quantum_exponent=op['correction_certificate']['binary_quantum_exponent'],
                 field_selection='all physical R fields in each affected native group; conservative support overapproximation',
                 source_projection=str(projection),targeted_recompute_coverage_certified=False,
                 physical_RC_qualified=False,release_qualified=False))
            verify(pins)
            save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(target):sha(target)},
                 negative_nodes=len(negatives),affected_global_fields=len(fields),targets=str(target),
                 all_negative_diagonal_states_resolved_to_original_R_fields=True,
                 full_matrix_passivity_verified=False,physical_RC_qualified=False,release_qualified=False))
            save(output/'status.json',dict(state='negative_C_state_fields_resolved',release_qualified=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_promotion',reason=repr(error),release_qualified=False));raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True,type=Path)
    run(parser.parse_args().output.resolve())
