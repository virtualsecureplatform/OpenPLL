#!/usr/bin/env python3
"""Retain native floating-conductor geometry and class records without collapse."""
import argparse
import json
from pathlib import Path
import time
from common import ROOT,save,sha
from compiled_charge import execute
from parallel_hash import sha_prefetch
from resources import lease
SOURCE=ROOT/'tools/native_rc_coverage/floating_geometry.cpp';HEADER=ROOT/'tools/charge_compiler/json.hpp'
def run(inventory,domain,export,output):
    inventory,domain,export,out=(Path(p).resolve() for p in (inventory,domain,export,output));out.mkdir(parents=True,exist_ok=False)
    started=time.clock_gettime(time.CLOCK_BOOTTIME);deadline=started+43200
    save(out/'owner.json',dict(wall_limit_s=43200,automatic_identical_retry=False,cpu_slots=2,memory_limit_GiB=8))
    def status(state,**extra):save(out/'status.json',dict(state=state,elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-started,release_qualified=False,**extra))
    try:
        status('waiting_for_resources')
        with lease(2,8,deadline):
            prior=json.loads((inventory/'assessment.json').read_text());dp=domain/'assessment.json';dh=sha(dp)
            if prior['shared_domain_sha256']!=dh or prior['input_sha256'].get(str(dp))!=dh:raise ValueError('inventory/domain receipt mismatch')
            domain_proof=json.loads(dp.read_text());export_proof=json.loads((export/'assessment.json').read_text());ext=domain/'trace/Prototype400_FilledCapacitanceView.ext';groups=export/'native/groups.jsonl';fields=inventory/'native/fields.jsonl'
            if prior['input_sha256'].get(str(groups))!=export_proof['artifacts'].get(str(groups)):raise ValueError('export inventory mismatch')
            wanted={str(ext):domain_proof['artifacts'][str(ext)],str(groups):export_proof['artifacts'][str(groups)],str(fields):prior['artifacts'][str(fields)],str(dp):dh}
            for p in (SOURCE,HEADER,Path(__file__).resolve(),inventory/'assessment.json',export/'assessment.json',*[Path(__file__).with_name(n) for n in ('common.py','compiled_charge.py','parallel_hash.py','resources.py')]):wanted[str(p)]=sha(p)
            for p,h in wanted.items():
                if sha_prefetch(p,deadline=deadline)!=h:raise ValueError('consumed EXT inventory input changed: '+p)
            save(out/'input_manifest.json',dict(input_sha256=wanted));binary=out/'floating_geometry';status('building_compiled_classifier');execute(['g++','-std=c++20','-O3','-Wall','-Wextra','-Wpedantic',SOURCE,'-o',binary],out/'build.log',deadline,8)
            cfg=out/'config.json';save(cfg,dict(ext=str(ext),groups=str(groups),inventory=str(fields),output=str(out/'native'),deadline_uptime=deadline))
            status('collecting_native_floating_geometry');execute([binary,cfg],out/'classify.log',deadline,8)
            result=json.loads((out/'native/summary.json').read_text())
            if result['unmatched_fields']!=prior['counts']['declared_component_without_port_device_or_native_R']:raise ValueError('unmatched field inventory count changed')
            for p,h in wanted.items():
                if sha_prefetch(p,deadline=deadline)!=h:raise ValueError('consumed EXT input changed during classification: '+p)
            result.update(input_sha256=wanted,shared_domain_sha256=dh,shared_geometry_sha256=prior['shared_geometry_sha256'],full_native_inputs_rehashed=False,physical_domain_complete=False,runtime_model_eligible=False,elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-started)
            result['artifacts']={str(p):sha(p) for p in (binary,cfg,out/'native/summary.json',*sorted((out/'native').glob('nodes_*.jsonl')))};save(out/'assessment.json',result);status('floating_geometry_inventory_complete_pending_GDS_correspondence');return result
    except BaseException as e:status('failed',reason=repr(e));raise
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('inventory','domain','export','output'):p.add_argument('--'+n,required=True,type=Path)
    a=p.parse_args();r=run(a.inventory,a.domain,a.export,a.output);print(json.dumps({k:r[k] for k in ('unmatched_fields','unique_native_conductors','native_types','elapsed_s')}))
