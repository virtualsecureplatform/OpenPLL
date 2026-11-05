#!/usr/bin/env python3
"""Parallel exact GDS geometry attribution for native unmatched conductors."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
import time
import pya
import klayout.dbcore
from common import ROOT,save,sha
from parallel_hash import sha_prefetch
sys.path.append(str(ROOT/'verification/prototype400'))
from parallel_geometry_jobs import run_jobs
from check_floating_gds_geometry import MATERIALS
WORKER=Path(__file__).with_name('check_floating_gds_geometry.py')
def run(inventory,domain,output):
    inventory,domain,out=(Path(p).resolve() for p in (inventory,domain,output));out.mkdir(parents=True,exist_ok=False)
    started=time.clock_gettime(time.CLOCK_BOOTTIME);deadline=started+43200
    save(out/'owner.json',dict(wall_limit_s=43200,automatic_identical_retry=False,max_parallel_jobs=7,per_job_memory_limit_GiB=8))
    def status(state='parallel_floating_geometry_running',**extra):save(out/'status.json',dict(state=state,elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-started,release_qualified=False,**extra))
    try:
        status('validating_same_geometry_inventory')
        proof=json.loads((inventory/'assessment.json').read_text());native=json.loads((domain/'assessment.json').read_text());dp=domain/'assessment.json'
        if proof['shared_domain_sha256']!=sha(dp) or proof['input_sha256'].get(str(dp))!=sha(dp):raise ValueError('floating inventory/domain mismatch')
        candidates=[(Path(p),h) for p,h in native['input_sha256'].items() if p.endswith('.gds')]
        if len(candidates)!=1 or candidates[0][1]!=proof['shared_geometry_sha256']:raise ValueError('floating inventory geometry mismatch')
        gds,gh=candidates[0];pins={str(gds):gh,str(dp):proof['shared_domain_sha256']}
        types=proof['native_types']
        if not types or not set(types)<=set(MATERIALS):raise ValueError('unsupported native material partition')
        if proof['nodes_with_multiple_spatial_field_keys'] or proof['nodes_without_exactly_one_nonzero_resistance_class']:raise ValueError('geometry needs explicit multi-class/material treatment')
        for t in types:
            p=inventory/'native'/('nodes_'+t+'.jsonl');pins[str(p)]=proof['artifacts'][str(p)]
        source_paths=[Path(__file__).resolve(),WORKER,ROOT/'verification/prototype400/parallel_geometry_jobs.py',*[Path(__file__).with_name(n) for n in ('common.py','parallel_hash.py','resources.py')]]
        for p in source_paths+[inventory/'assessment.json',Path(sys.executable).resolve(),Path(pya.__file__).resolve(),Path(klayout.dbcore.__file__).resolve(),ROOT/'build/apptainer/openpll-release-modern.sif']:pins[str(p)]=sha(p)
        for p,h in pins.items():
            if sha_prefetch(p,deadline=deadline)!=h:raise ValueError('floating geometry input changed: '+p)
        save(out/'input_manifest.json',dict(input_sha256=pins,shared_geometry_sha256=gh,native_internal_unit_um=.005))
        jobs=[dict(label=t,cpus=1,memory_gib=8,command=[sys.executable,WORKER,'--gds',gds,'--nodes',inventory/'native'/('nodes_'+t+'.jsonl'),'--output',out/t,'--native-type',t,'--deadline-uptime',str(deadline)]) for t in types]
        status();source_pins={str(p):pins[str(p)] for p in source_paths};run_jobs(jobs,out,source_pins,deadline,workers=7,update=status)
        results={};totals=Counter()
        for t,n in types.items():
            r=json.loads((out/t/'summary.json').read_text())
            if r['limited_to_prefix'] or r['counts']['nodes']!=n:raise ValueError('floating geometry partition coverage differs')
            results[t]=r;totals.update(r['counts'])
        if totals['nodes']!=proof['unique_native_conductors']:raise ValueError('floating geometry conductor coverage differs')
        for p,h in pins.items():
            if sha_prefetch(p,deadline=deadline)!=h:raise ValueError('floating geometry input changed while checking: '+p)
        result=dict(input_sha256=pins,shared_domain_sha256=proof['shared_domain_sha256'],shared_geometry_sha256=gh,counts=dict(totals),per_native_type=results,all_native_conductors_exact_rectangles=all(r['geometry_inventory_matches_all_nodes'] for r in results.values()),finite_R_basis_qualified=False,resistance_units_and_PVT_qualified=False,unlocated_arithmetic_attachment_qualified=False,physical_domain_complete=False,runtime_model_eligible=False,release_qualified=False,elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-started)
        artifacts=[p for t in types for p in (out/t/'summary.json',out/t/'nodes.jsonl')];result['artifacts']={str(p):sha(p) for p in artifacts};save(out/'assessment.json',result);status('floating_geometry_audit_complete_pending_finite_R_basis');return result
    except BaseException as e:status('failed',reason=repr(e));raise
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('inventory','domain','output'):p.add_argument('--'+n,required=True,type=Path)
    a=p.parse_args();r=run(a.inventory,a.domain,a.output);print(json.dumps({k:r[k] for k in ('counts','all_native_conductors_exact_rectangles','elapsed_s')}))
