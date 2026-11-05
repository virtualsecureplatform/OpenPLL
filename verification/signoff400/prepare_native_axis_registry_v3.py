#!/usr/bin/env python3
"""Stage every native axis chain, retaining numeric/symbolic/deferred states.

Uses bounded local scratch for the compiled pass, then publishes exact artifacts.
This is a candidate registry, not physical snapshot or RC qualification.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from common import ROOT,save,sha
from compiled_charge import execute
from resources import lease
from nominal_sheet_resistance_v3 import parse
SOURCE=ROOT/'tools/native_rc_coverage/prepare_axis_registry.cpp';HEADER=ROOT/'tools/charge_compiler/json.hpp';TECH=ROOT/'build/timing450/pdk/sky130A/libs.tech/magic/sky130A.tech'
def run(chains,registration,domain,output):
    chains,registration,domain,out=(Path(p).resolve() for p in (chains,registration,domain,output));out.mkdir(parents=True,exist_ok=False);start=time.clock_gettime(time.CLOCK_BOOTTIME);deadline=start+43200;scratch=None
    def status(state,**extra):save(out/'status.json',dict(state=state,release_qualified=False,elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-start,**extra))
    save(out/'owner.json',dict(wall_limit_s=43200,automatic_identical_retry=False,cpu_slots=2,memory_limit_GiB=8,local_scratch=True))
    try:
        with lease(2,8,deadline):
            status('validating_current_chain_and_nominal_technology_lineage');c=json.loads((chains/'assessment.json').read_text());r=json.loads((registration/'assessment.json').read_text());d=json.loads((domain/'assessment.json').read_text())
            if not c['all_wire_segments_preserved'] or c['input_sha256'].get(str(registration/'assessment.json'))!=sha(registration/'assessment.json') or r['input_sha256'].get(str(domain/'assessment.json'))!=sha(domain/'assessment.json'):raise ValueError('axis registry input lineage mismatch')
            task=domain/'trace/extract.tcl'
            if d['input_sha256'].get(str(TECH))!=sha(TECH) or d['input_sha256'].get(str(task))!=sha(task) or 'extract style ngspice()' not in task.read_text():raise ValueError('exact nominal R technology/style required')
            values=parse(TECH.read_text());source=chains/'native/chains.jsonl';source_hash=c['artifacts'][str(source)];size=source.stat().st_size
            if shutil.disk_usage('/tmp').free<4*size+32*1024**3:raise ValueError('local scratch reserve unavailable')
            scratch=Path(tempfile.mkdtemp(prefix='openpll-axis-registry-',dir='/tmp'));save(out/'staging.json',dict(path=str(scratch),source=str(source),source_sha256=source_hash,success_cleanup_after_verified_publish=True))
            compiler=Path(shutil.which('g++')).resolve();arch=subprocess.check_output([compiler,'-print-multiarch'],text=True).strip();libraries=[Path(subprocess.check_output([compiler,'-print-file-name='+n],text=True).strip()).resolve() for n in ('libgmp.so','libgmpxx.so')]
            pins={str(source):source_hash}
            paths=[SOURCE,HEADER,TECH,task,chains/'assessment.json',registration/'assessment.json',domain/'assessment.json',Path(__file__).resolve(),compiler,Path('/usr/include/gmpxx.h'),Path('/usr/include')/arch/'gmp.h',*libraries,*[Path(__file__).with_name(n) for n in ('common.py','compiled_charge.py','resources.py','nominal_sheet_resistance.py','nominal_sheet_resistance_v2.py','nominal_sheet_resistance_v3.py')]]
            for p in paths:pins[str(p)]=sha(p)
            status('copying_once_to_local_scratch');local=scratch/'chains.jsonl';shutil.copyfile(source,local)
            if sha(local)!=source_hash:raise ValueError('staged chain bytes do not match complete producer receipt')
            save(out/'input_manifest.json',dict(input_sha256=pins));save(out/'nominal_sheet_values.json',dict(unit='milliohms_per_square',values={k:str(v) for k,v in values.items()},PVT_qualified=False));binary=scratch/'prepare_axis_registry';command=[compiler,'-std=c++20','-O3','-Wall','-Wextra','-Wpedantic',SOURCE,'-lgmpxx','-lgmp','-o',binary]
            status('building_compiled_registry_preparer');execute(command,scratch/'build.log',deadline,8);cfg=scratch/'execution_config.json';save(cfg,dict(chains=str(local),nominal_sheet_values={k:str(v) for k,v in values.items()},output=str(scratch/'native'),deadline_uptime=deadline))
            status('preparing_all_numeric_symbolic_and_deferred_axes');execute([binary,cfg],scratch/'native.log',deadline,8);result=json.loads((scratch/'native/summary.json').read_text())
            if result['source_chains']!=c['tile_axis_chains'] or result['native_segments_referenced']!=c['wire_segments']:raise ValueError('axis registry dropped a chain or native segment')
            status('publishing_verified_registry');publish=[(binary,out/'prepare_axis_registry'),(scratch/'build.log',out/'build.log'),(cfg,out/'execution_config.json'),(scratch/'native.log',out/'native.log'),(scratch/'native/summary.json',out/'native/summary.json'),(scratch/'native/axis_registry.jsonl',out/'native/axis_registry.jsonl')]
            artifacts={}
            for src,dst in publish:
                dst.parent.mkdir(parents=True,exist_ok=True)
                with dst.open('xb') as target,src.open('rb') as origin:shutil.copyfileobj(origin,target,length=8*1024**2)
                h=sha(src)
                if sha(dst)!=h:raise ValueError('published registry differs from local result')
                artifacts[str(dst)]=h
            for p,h in pins.items():
                if sha(p)!=h:raise ValueError('axis registry input changed during construction: '+p)
            save(out/'build.json',dict(command=list(map(str,command)),compiler_version=subprocess.check_output([compiler,'--version'],text=True),input_sha256={str(p):pins[str(p)] for p in (SOURCE,HEADER,compiler,*libraries)},artifacts={str(out/'prepare_axis_registry'):artifacts[str(out/'prepare_axis_registry')]}))
            result.update(input_sha256=pins,artifacts=artifacts,all_source_chains_accounted=True,nominal_nondevice_values_only=True,local_scratch_bytes_equal_published=True,full_native_inputs_rehashed=False,elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-start)
            save(out/'assessment.json',result);shutil.rmtree(scratch);status('axis_registry_prepared_pending_physical_snapshot_material_and_C_qualification');return result
    except BaseException as e:status('failed',reason=repr(e),retained_staging_directory=str(scratch) if scratch else None);raise
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('chains','registration','domain','output'):p.add_argument('--'+n,required=True,type=Path)
    a=p.parse_args();r=run(a.chains,a.registration,a.domain,a.output);print(json.dumps({k:r[k] for k in ('source_chains','geometric_axes_prepared','new_latent_end_states','nominal_numeric_end_resistors','symbolic_end_resistors','chains_by_preparation_state','elapsed_s')}))
