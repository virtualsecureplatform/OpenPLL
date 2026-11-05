#!/usr/bin/env python3
"""Finish exact output comparison after a completed merge; never rerun merging."""
import argparse
import json
from pathlib import Path
import time
from common import ROOT,save,sha
from compiled_charge import execute
from parallel_hash import sha_prefetch
from resources import lease
SOURCE=ROOT/'tools/charge_compiler/merge_buffered.cpp'
HEADER=SOURCE.with_name('json.hpp')
BYTE_SOURCE=SOURCE.with_name('compare_bytes.cpp')
def run(candidate,reference,output):
    candidate,reference,out=(Path(p).resolve() for p in (candidate,reference,output));out.mkdir(parents=True,exist_ok=False)
    settings=json.loads((candidate/'merge.config.json').read_text());deadline=settings['deadline_uptime'];started=time.clock_gettime(time.CLOCK_BOOTTIME)
    save(out/'owner.json',dict(original_owner=str(candidate/'owner.json'),original_deadline_uptime=deadline,total_budget_restarted=False,automatic_identical_retry=False,merge_rerun=False))
    def status(state,**extra):save(out/'status.json',dict(state=state,elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-started,release_qualified=False,**extra))
    try:
        status('waiting_for_comparison_resources')
        with lease(2,4,deadline):
            expected=json.loads((candidate/'input_manifest.json').read_text())['input_sha256'];proof=json.loads((reference/'assessment.json').read_text());pins={}
            # Both original consumed-shard inventories and the reference remain exact.
            for table in (expected,proof['input_sha256'],proof['artifacts']):
                for p,h in table.items():
                    if p in pins:
                        if pins[p]!=h:raise ValueError('conflicting original input pins')
                        continue
                    if sha_prefetch(p,deadline=deadline)!=h:raise ValueError('original comparison input changed: '+p)
                    pins[p]=h
            consumed=[p for p in proof['input_sha256'] if '/worker_' in p and p.endswith(('/fields.json','/collapsed_matrix_ledger.json'))]
            for p in consumed:
                if expected.get(p)!=proof['input_sha256'][p]:raise ValueError('reference consumes different shard files')
            paths=[candidate/'input_manifest.json',candidate/'merge.config.json',candidate/'merge_summary.json',candidate/'operators_manifest.json',reference/'assessment.json',SOURCE,HEADER,BYTE_SOURCE,Path(__file__).resolve()]
            n=len(json.loads((candidate/'operators_manifest.json').read_text())['shards'])
            names=['fields.json','collapsed_matrix_ledger.json']+[f'worker_{i}_field_map.json' for i in range(n)]
            paths += [candidate/name for name in names]
            for p in paths:pins[str(p)]=sha_prefetch(p,deadline=deadline)
            save(out/'input_manifest.json',dict(input_sha256=pins))
            binary=out/'compare_bytes';status('building_verified_comparator');execute(['g++','-std=c++20','-O3',BYTE_SOURCE,'-o',binary],out/'build.log',deadline,4)
            json_binary=None
            status('comparing_all_fields_mappings_and_numeric_bits');compared={}
            for name in names:
                if name.endswith('_field_map.json'):
                    if sha(candidate/name)!=sha(reference/name):raise ValueError('field map differs')
                else:
                    log=out/(name+'.compare.log')
                    if pins[str(candidate/name)]==pins[str(reference/name)]:
                        execute([binary,reference/name,candidate/name,deadline],log,deadline,4)
                        evidence=json.loads(log.read_text());evidence.update(numeric_values_bitwise_equal=True,reference_rows=proof['global_fields' if name=='fields.json' else 'global_ledger_rows'],row_count_basis='pinned reference receipt; literal byte identity',comparison_method='literal_byte_comparison')
                    else:
                        if json_binary is None:
                            json_binary=out/'compare_json';execute(['g++','-std=c++20','-O3','-fopenmp','-fno-fast-math','-ffp-contract=off',SOURCE,'-o',json_binary],out/'json_build.log',deadline,4)
                        execute([json_binary,'compare',reference/name,candidate/name,deadline],log,deadline,4);evidence=json.loads(log.read_text());evidence['comparison_method']='strict_parsed_numeric_bits'
                    compared[name]=evidence
            actual=json.loads((candidate/'operators_manifest.json').read_text());ref=json.loads((reference/'operators_manifest.json').read_text())
            for key in ('counts','components','arithmetic_residual_absolute_native_cap_units'):
                if actual[key]!=ref[key]:raise ValueError('aggregate differs: '+key)
            for p,h in pins.items():
                if sha_prefetch(p,deadline=deadline)!=h:raise ValueError('comparison input changed during execution: '+p)
            result=dict(input_sha256=pins,artifacts={str(p):sha(p) for p in [binary,*([json_binary] if json_binary else []),*out.glob('*.compare.log')]},full_reference_numeric_comparison=True,comparisons=compared,field_maps_compared=n,merge_rerun=False,original_deadline_preserved=True,full_native_inputs_rehashed=False,physical_domain_complete=False,runtime_model_eligible=False,release_qualified=False,elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-started)
            save(out/'assessment.json',result);status('full_reference_comparison_passed');return result
    except BaseException as e:status('failed',reason=repr(e));raise
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('candidate','reference','output'):p.add_argument('--'+n,required=True,type=Path)
    a=p.parse_args();r=run(a.candidate,a.reference,a.output);print(json.dumps(r['comparisons']))
