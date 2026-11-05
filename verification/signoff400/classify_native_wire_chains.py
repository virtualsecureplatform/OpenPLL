#!/usr/bin/env python3
"""Classify every retained native wire segment without selecting snapshots."""
import argparse
import json
from pathlib import Path
import time
from common import ROOT,save,sha
from compiled_charge import execute
from parallel_hash import sha_prefetch
from resources import lease
SOURCE=ROOT/'tools/native_rc_coverage/classify_wire_chains.cpp';HEADER=ROOT/'tools/charge_compiler/json.hpp'
def run(registration,output):
    registration,out=(Path(p).resolve() for p in (registration,output));out.mkdir(parents=True,exist_ok=False);start=time.clock_gettime(time.CLOCK_BOOTTIME);deadline=start+43200
    save(out/'owner.json',dict(wall_limit_s=43200,automatic_identical_retry=False,cpu_slots=2,memory_limit_GiB=8))
    def status(state,**extra):save(out/'status.json',dict(state=state,release_qualified=False,elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-start,**extra))
    try:
        with lease(2,8,deadline):
            status('validating_complete_branch_registration');r=json.loads((registration/'assessment.json').read_text())
            if not r['all_native_branch_records_emitted'] or not r['all_wire_creation_records_emitted']:raise ValueError('complete native registration required')
            wires=registration/'native/wire_creation_records.jsonl';pins={str(wires):r['artifacts'][str(wires)]}
            for p in (SOURCE,HEADER,Path(__file__).resolve(),registration/'assessment.json',*[Path(__file__).with_name(n) for n in ('common.py','compiled_charge.py','parallel_hash.py','resources.py')]):pins[str(p)]=sha(p)
            for p,h in pins.items():
                if sha_prefetch(p,deadline=deadline)!=h:raise ValueError('wire-chain input changed: '+p)
            save(out/'input_manifest.json',dict(input_sha256=pins));binary=out/'classify_wire_chains';status('building_compiled_chain_inventory');execute(['g++','-std=c++20','-O3','-Wall','-Wextra','-Wpedantic',SOURCE,'-o',binary],out/'build.log',deadline,8)
            cfg=out/'config.json';save(cfg,dict(wires=str(wires),output=str(out/'native'),deadline_uptime=deadline));status('classifying_all_retained_wire_chains');execute([binary,cfg],out/'inventory.log',deadline,8)
            result=json.loads((out/'native/summary.json').read_text())
            if result['wire_segments']!=r['wire_branches'] or result['emitted_wire_segments']!=r['wire_branches']:raise ValueError('wire-chain coverage differs from native registration')
            for p,h in pins.items():
                if sha_prefetch(p,deadline=deadline)!=h:raise ValueError('wire-chain input changed during inventory: '+p)
            result.update(input_sha256=pins,artifacts={str(p):sha(p) for p in (binary,cfg,out/'native/summary.json',out/'native/chains.jsonl')},full_native_inputs_rehashed=False,elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-start)
            save(out/'assessment.json',result);status('wire_chain_inventory_complete_pending_domain_treatment',chains=result['tile_axis_chains']);return result
    except BaseException as e:status('failed',reason=repr(e));raise
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--registration',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args();r=run(a.registration,a.output);print(json.dumps({k:r[k] for k in ('wire_segments','tile_axis_chains','chains_by_state','elapsed_s')}))
