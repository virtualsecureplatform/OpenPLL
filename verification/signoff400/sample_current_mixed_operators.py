#!/usr/bin/env python3
"""Select real signed operator controls from fully rehashed retained shard files."""
import argparse
import json
from pathlib import Path
import time
from common import ROOT,save,sha
from parallel_hash import sha_prefetch
from compiled_charge import execute
from resources import lease
SOURCE=ROOT/'tools/native_rc_coverage/sample_mixed_operators.cpp';HEADER=ROOT/'tools/charge_compiler/json.hpp'
def run(charge,geometry,output,shard=0,max_records=2000000,per_bucket=1,original_owner=None,R_index=None):
    charge,geometry,out=(Path(p).resolve() for p in (charge,geometry,output));out.mkdir(parents=True,exist_ok=False);start=time.clock_gettime(time.CLOCK_BOOTTIME);deadline=start+43200
    if original_owner is not None:
        original_owner=Path(original_owner).resolve();previous=json.loads(original_owner.read_text())
        remaining=original_owner.stat().st_mtime+previous['wall_limit_s']-time.time()-1
        deadline=min(deadline,time.clock_gettime(time.CLOCK_BOOTTIME)+remaining)
        if remaining<=0:raise TimeoutError('original sampler deadline exhausted')
    save(out/'owner.json',dict(wall_limit_s=43200,deadline_uptime=deadline,original_owner=str(original_owner) if original_owner else None,original_deadline_preserved=original_owner is not None,automatic_identical_retry=False,cpu_slots=2,memory_limit_GiB=8,shard=shard,max_records=max_records,per_bucket=per_bucket,windows=16))
    def status(state):save(out/'status.json',dict(state=state,elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-start,release_qualified=False))
    try:
        with lease(2,8,deadline):
            status('validating_current_compiled_native_and_geometry_lineage')
            merge=charge/'assessment.json';m=json.loads(merge.read_text());g=json.loads((geometry/'assessment.json').read_text())
            manifest=charge/'operators_manifest.json'
            if sha(manifest)!=m['artifacts'][str(manifest)]:raise ValueError('operator manifest changed')
            metadata=json.loads(manifest.read_text());spec=metadata['shards'][shard];operators=Path(spec['operators']).resolve();worker=operators.parent/'assessment.json'
            if m['artifacts'].get(str(worker))!=sha(worker):raise ValueError('compiled worker receipt changed')
            native=Path(json.loads((charge/'owner.json').read_text())['source'])/'assessment.json'
            if m['input_sha256'].get(str(native))!=sha(native):raise ValueError('compiled native source changed')
            n=json.loads(native.read_text());gds=[(p,h) for p,h in g['input_sha256'].items() if p.endswith('.gds')]
            if len(gds)!=1 or n['input_sha256'].get(gds[0][0])!=gds[0][1]:raise ValueError('C and geometry do not pin one identical layout')
            w=json.loads(worker.read_text());wpins=w['artifacts'];mpins=m['artifacts']
            fields=Path(metadata['fields']).resolve();mapping=Path(spec['field_map']).resolve()
            pins={str(operators):wpins[str(operators)],str(fields):mpins[str(fields)],str(mapping):mpins[str(mapping)],str(native):sha(native)}
            R_index=Path(R_index).resolve();R_receipt=R_index.parent/'assessment.json';R_report=json.loads(R_receipt.read_text())
            pins[str(R_index)]=R_report['artifacts'][str(R_index)];pins[str(R_receipt)]=sha(R_receipt)
            expected_map=Path(R_report['source_mapping'])/'assessment.json'
            if R_report['input_sha256'].get(str(expected_map))!=sha(expected_map):raise ValueError('R index map receipt changed')
            if json.loads(expected_map.read_text())['input_sha256'].get(str(merge))!=sha(merge):raise ValueError('R index and C compiler lineage differ')
            partitions=[]
            for t in g['per_native_type']:
                p=geometry/t/'nodes.jsonl';pins[str(p)]=g['artifacts'][str(p)];partitions.append(dict(nodes=str(p),native_type=t))
            for p in (SOURCE,HEADER,Path(__file__).resolve(),charge/'assessment.json',geometry/'assessment.json',merge,manifest,worker,*[Path(__file__).with_name(n) for n in ('common.py','parallel_hash.py','compiled_charge.py','resources.py')]):pins[str(p)]=sha(p)
            if original_owner is not None:pins[str(original_owner)]=sha(original_owner)
            for p,h in pins.items():
                if sha_prefetch(p,deadline=deadline)!=h:raise ValueError('selected sampler input changed: '+p)
            save(out/'input_manifest.json',dict(input_sha256=pins));binary=out/'sample_sheet_operators';status('building_compiled_sampler');execute(['g++','-std=c++20','-O3','-Wall','-Wextra','-Wpedantic',SOURCE,'-o',binary],out/'build.log',deadline,8)
            cfg=out/'config.json';save(cfg,dict(R_index=str(R_index),fields=str(fields),field_map=str(mapping),geometry_partitions=partitions,operators=str(operators),output=str(out/'native'),deadline_uptime=deadline,max_records=max_records,per_bucket=per_bucket,windows=16))
            status('selecting_indexed_signed_operator_prefix');execute([binary,cfg],out/'sample.log',deadline,8)
            for p,h in pins.items():
                if sha_prefetch(p,deadline=deadline)!=h:raise ValueError('sampler input changed during execution: '+p)
            result=json.loads((out/'native/summary.json').read_text());result.update(input_sha256=pins,artifacts={str(p):sha(p) for p in (binary,cfg,out/'native/cases.jsonl',out/'native/summary.json')},shared_geometry_sha256=g['shared_geometry_sha256'],selected_operator_file_fully_rehashed=True,full_native_inputs_rehashed=False,full_layout_capacitance_attachment_qualified=False,runtime_model_eligible=False,elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-start)
            save(out/'assessment.json',result);status('native_operator_samples_complete_pending_integration_controls');return result
    except BaseException as e:status('failed');raise
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('charge','geometry','output'):p.add_argument('--'+n,required=True,type=Path)
    p.add_argument('--R-index',required=True,type=Path)
    p.add_argument('--original-owner',type=Path);p.add_argument('--shard',type=int,default=0);p.add_argument('--max-records',type=int,default=2000000);a=p.parse_args();r=run(a.charge,a.geometry,a.output,a.shard,a.max_records,original_owner=a.original_owner,R_index=a.R_index);print(json.dumps({k:r[k] for k in ('scanned_operator_rows','selected_cases','sample_buckets','elapsed_s')}))
