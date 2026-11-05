#!/usr/bin/env python3
"""Compiled exact-label C/R inventory; never a spatial/electrical qualification."""
import argparse
import json
from pathlib import Path
import time
from common import ROOT,save,sha
from compiled_charge import execute
from parallel_hash import sha_prefetch
from resources import lease
SOURCE=ROOT/'tools/native_rc_coverage/main.cpp'
HEADER=ROOT/'tools/charge_compiler/json.hpp'

def run(charge,domain,index,export,output):
    charge,domain,index,export,out=(Path(p).resolve() for p in (charge,domain,index,export,output))
    out.mkdir(parents=True,exist_ok=False);started=time.clock_gettime(time.CLOCK_BOOTTIME);deadline=started+43200
    def status(state,**extra):save(out/'status.json',dict(state=state,elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-started,release_qualified=False,**extra))
    save(out/'owner.json',dict(wall_limit_s=43200,automatic_identical_retry=False,cpu_slots=2,memory_limit_GiB=8))
    try:
        status('waiting_for_resources')
        with lease(2,8,deadline):
            proofs={name:json.loads((p/'assessment.json').read_text()) for name,p in [('charge',charge),('domain',domain),('index',index),('export',export)]}
            consumed={}
            def consume(p,expected):
                p=Path(p).resolve();actual=sha_prefetch(p,deadline=deadline)
                if actual!=expected:raise ValueError('consumed input changed: '+str(p))
                consumed[str(p)]=actual
            for p in (charge,domain,index,export):consume(p/'assessment.json',sha(p/'assessment.json'))
            dp=str(domain/'assessment.json');dh=consumed[dp]
            for name in ('charge','index'):
                if proofs[name]['input_sha256'].get(dp)!=dh:raise ValueError('C/R inventory does not share the exact retained domain receipt')
            gds=[(p,h) for p,h in proofs['domain']['input_sha256'].items() if p.endswith('.gds')]
            if len(gds)!=1:raise ValueError('one explicit domain geometry required')
            gp,gh=gds[0]
            if proofs['charge']['input_sha256'].get(gp)!=gh:raise ValueError('charge and R geometry hashes differ')
            consume(gp,gh)
            provenance=str(domain/'trace/R_provenance.log')
            expected=proofs['domain']['artifacts'][provenance]
            if proofs['export']['input_sha256'].get(provenance)!=expected or proofs['index']['input_sha256'].get(provenance)!=expected:
                raise ValueError('export and indexed snapshots do not share domain provenance')
            # Shared pinned provenance establishes lineage; the inventory consumes
            # only its derived groups/tiles, not all native 200+GB traces.
            selected=[(charge/'fields.json','charge'),(index/'tile_domains.jsonl','index'),(export/'native/groups.jsonl','export')]
            status('validating_consumed_inventory_artifacts')
            for p,name in selected:consume(p,proofs[name]['artifacts'][str(p)])
            for p in (SOURCE,HEADER,Path(__file__).resolve(),*[Path(__file__).with_name(n) for n in ('common.py','compiled_charge.py','parallel_hash.py','resources.py')]):consume(p,sha(p))
            save(out/'input_manifest.json',dict(input_sha256=consumed,shared_geometry_sha256=gh,shared_domain_sha256=dh))
            binary=out/'native_rc_coverage';command=['g++','-std=c++20','-O3','-Wall','-Wextra','-Wpedantic','-fno-fast-math','-ffp-contract=off',str(SOURCE),'-o',str(binary)]
            status('building_compiled_inventory');execute(command,out/'build.log',deadline,8)
            cfg=out/'config.json';save(cfg,dict(fields=str(charge/'fields.json'),groups=str(export/'native/groups.jsonl'),tiles=str(index/'tile_domains.jsonl'),output=str(out/'native'),deadline_uptime=deadline))
            status('inventorying_every_field_and_snapshot');execute([binary,cfg],out/'inventory.log',deadline,8)
            for p,h in consumed.items():
                if sha_prefetch(p,deadline=deadline)!=h:raise ValueError('inventory input changed during execution: '+p)
            result=json.loads((out/'native/summary.json').read_text())
            for actual,expected in [('native_snapshots',proofs['index']['native_groups']),('native_conductor_labels',proofs['index']['original_conductors']),('native_tiles',proofs['index']['domain_counts']['domains'])]:
                if result[actual]!=expected:raise ValueError('indexed snapshot inventory count differs: '+actual)
            result.update(input_sha256=consumed,shared_geometry_sha256=gh,shared_domain_sha256=dh,full_native_inputs_rehashed=False,elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-started)
            result['artifacts']={str(p):sha(p) for p in (binary,cfg,out/'native/summary.json',out/'native/fields.jsonl')}
            save(out/'assessment.json',result);status('inventory_complete_pending_physical_domain_qualification',fields=result['fields']);return result
    except BaseException as e:status('failed',reason=repr(e));raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('charge','domain','index','export','output'):p.add_argument('--'+n,required=True,type=Path)
    a=p.parse_args();r=run(a.charge,a.domain,a.index,a.export,a.output);print(json.dumps({k:r[k] for k in ('fields','counts','elapsed_s')}))
