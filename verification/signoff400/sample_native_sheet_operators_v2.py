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
SOURCE=ROOT/'tools/native_rc_coverage/sample_sheet_operators_v2.cpp';HEADER=ROOT/'tools/charge_compiler/json.hpp'
def run(charge,geometry,output,shard=0,max_records=2000000,per_bucket=2,original_owner=None):
    charge,geometry,out=(Path(p).resolve() for p in (charge,geometry,output));out.mkdir(parents=True,exist_ok=False);start=time.clock_gettime(time.CLOCK_BOOTTIME);deadline=start+43200
    if original_owner is not None:
        original_owner=Path(original_owner).resolve();previous=json.loads(original_owner.read_text())
        remaining=original_owner.stat().st_mtime+previous['wall_limit_s']-time.time()-1
        deadline=min(deadline,time.clock_gettime(time.CLOCK_BOOTTIME)+remaining)
        if remaining<=0:raise TimeoutError('original sampler deadline exhausted')
    save(out/'owner.json',dict(wall_limit_s=43200,deadline_uptime=deadline,original_owner=str(original_owner) if original_owner else None,original_deadline_preserved=original_owner is not None,automatic_identical_retry=False,cpu_slots=2,memory_limit_GiB=8,shard=shard,max_records=max_records,per_bucket=per_bucket))
    def status(state):save(out/'status.json',dict(state=state,elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-start,release_qualified=False))
    try:
        with lease(2,8,deadline):
            status('validating_same_geometry_and_selected_shard_lineage');c=json.loads((charge/'assessment.json').read_text());g=json.loads((geometry/'assessment.json').read_text());canonical={str(Path(p).resolve()):h for p,h in c['input_sha256'].items()}
            merge=Path(c['compiled_merge_assessment']).resolve()
            if canonical.get(str(merge))!=sha(merge):raise ValueError('compiled merge receipt identity mismatch')
            m=json.loads(merge.read_text());manifest=merge.parent/'operators_manifest.json'
            if sha(manifest)!=m['artifacts'][str(manifest)]:raise ValueError('operator manifest changed')
            metadata=json.loads(manifest.read_text());spec=metadata['shards'][shard];operators=Path(spec['operators']).resolve();worker=operators.parent/'assessment.json'
            if canonical.get(str(worker))!=sha(worker):raise ValueError('compiled worker receipt identity mismatch')
            w=json.loads(worker.read_text());wpins={str(Path(p).resolve()):h for p,h in w['artifacts'].items()};mpins={str(Path(p).resolve()):h for p,h in m['artifacts'].items()}
            gds=[(p,h) for p,h in g['input_sha256'].items() if p.endswith('.gds')]
            if len(gds)!=1 or canonical.get(str(Path(gds[0][0]).resolve()))!=gds[0][1]:raise ValueError('compiled fields and floating geometry do not share the same GDS')
            fields=Path(metadata['fields']).resolve();mapping=Path(spec['field_map']).resolve();pins={str(operators):wpins[str(operators)],str(fields):mpins[str(fields)],str(mapping):mpins[str(mapping)]}
            partitions=[]
            for t in g['per_native_type']:
                p=geometry/t/'nodes.jsonl';pins[str(p)]=g['artifacts'][str(p)];partitions.append(dict(nodes=str(p),native_type=t))
            for p in (SOURCE,HEADER,Path(__file__).resolve(),charge/'assessment.json',geometry/'assessment.json',merge,manifest,worker,*[Path(__file__).with_name(n) for n in ('common.py','parallel_hash.py','compiled_charge.py','resources.py')]):pins[str(p)]=sha(p)
            if original_owner is not None:pins[str(original_owner)]=sha(original_owner)
            for p,h in pins.items():
                if sha_prefetch(p,deadline=deadline)!=h:raise ValueError('selected sampler input changed: '+p)
            save(out/'input_manifest.json',dict(input_sha256=pins));binary=out/'sample_sheet_operators';status('building_compiled_sampler');execute(['g++','-std=c++20','-O3','-Wall','-Wextra','-Wpedantic',SOURCE,'-o',binary],out/'build.log',deadline,8)
            cfg=out/'config.json';save(cfg,dict(fields=str(fields),field_map=str(mapping),geometry_partitions=partitions,operators=str(operators),output=str(out/'native'),deadline_uptime=deadline,max_records=max_records,per_bucket=per_bucket))
            status('selecting_indexed_signed_operator_prefix');execute([binary,cfg],out/'sample.log',deadline,8)
            for p,h in pins.items():
                if sha_prefetch(p,deadline=deadline)!=h:raise ValueError('sampler input changed during execution: '+p)
            result=json.loads((out/'native/summary.json').read_text());result.update(input_sha256=pins,artifacts={str(p):sha(p) for p in (binary,cfg,out/'native/cases.jsonl',out/'native/summary.json')},shared_geometry_sha256=g['shared_geometry_sha256'],selected_operator_file_fully_rehashed=True,full_native_inputs_rehashed=False,full_layout_capacitance_attachment_qualified=False,runtime_model_eligible=False,elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-start)
            save(out/'assessment.json',result);status('native_operator_samples_complete_pending_integration_controls');return result
    except BaseException as e:status('failed');raise
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('charge','geometry','output'):p.add_argument('--'+n,required=True,type=Path)
    p.add_argument('--original-owner',type=Path);p.add_argument('--shard',type=int,default=0);p.add_argument('--max-records',type=int,default=2000000);a=p.parse_args();r=run(a.charge,a.geometry,a.output,a.shard,a.max_records,original_owner=a.original_owner);print(json.dumps({k:r[k] for k in ('scanned_operator_rows','selected_cases','sample_buckets','elapsed_s')}))
