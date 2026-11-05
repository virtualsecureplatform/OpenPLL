"""Assemble unchanged native core R values into bounded parallel G runs."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shutil
import struct
import tempfile
import time
from common import ROOT,save,sha
from compiled_charge import execute
from resources import lease


def run(core,mapping,matrix_controls,merger_upgrade,output):
    core,mapping,matrix_controls,merger_upgrade,out=(p.resolve() for p in (core,mapping,matrix_controls,merger_upgrade,output))
    out.mkdir(parents=True,exist_ok=False);scratch=Path(tempfile.mkdtemp(prefix='openpll-native-core-G-',dir='/tmp'))
    (out/'native').symlink_to(scratch,target_is_directory=True)
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    proofs=[p/'assessment.json' for p in (core,mapping,matrix_controls,merger_upgrade)]
    native,maps,check,upgrade=[json.loads(p.read_text()) for p in proofs]
    if not native['final_native_core_R_voltage_namespace_join_complete'] or native['results']['nodes_requiring_R_only_voltage_union']:
        raise ValueError('complete native R namespace required')
    if native['input_sha256'].get(str(proofs[1]))!=sha(proofs[1]) or not check['matrix_structure_controls_pass'] or not upgrade['actual_operator_merge_bytes_identical']:
        raise ValueError('matching native namespace and controlled numeric tools required')
    branches=next(Path(p) for p in native['artifacts'] if p.endswith('/native_core_branches.jsonl'))
    merger=Path(upgrade['merger_binary']);auditor=matrix_controls/'audit_sparse_matrix'
    compiler=Path(shutil.which('g++')).resolve();source=ROOT/'tools/sheet_charge/compile_native_core_G.cpp'
    paths=[*proofs,branches,merger,auditor,compiler,source,source.parent/'sparse_runs_v2.hpp',
           ROOT/'tools/charge_compiler/json.hpp',Path(__file__).resolve()]
    def status(state,**extra):save(out/'status.json',dict(state=state,release_qualified=False,**extra))
    try:
        with lease(8,16,deadline):
            with ThreadPoolExecutor(max_workers=8) as pool:pins=dict(zip(map(str,paths),pool.map(sha,paths)))
            if pins[str(branches)]!=native['artifacts'][str(branches)] or pins[str(merger)]!=upgrade['input_sha256'][str(merger)] or pins[str(auditor)]!=check['artifacts'][str(auditor)]:
                raise ValueError('native conductance input changed')
            binary=out/'compile_native_core_G'
            execute([compiler,'-std=c++20','-O3','-fopenmp','-Wall','-Wextra','-Wpedantic','-fno-fast-math',
                     '-ffp-contract=off',source,'-o',binary],out/'build.log',deadline,8)
            artifacts={}
            def merge(runs,root,label,json_output=False):
                current=runs;level=0
                while len(current)>1 or (json_output and level==0):
                    next_level=[]
                    for start in range(0,len(current),128):
                        cfg=root/f'{label}_{level}_{start}.json';result=root/f'{label}_{level}_{start}.bin'
                        settings=dict(inputs=list(map(str,current[start:start+128])),output=str(result),deadline_uptime=deadline)
                        if json_output:settings['json_output']=str(root/(label+'.jsonl'))
                        save(cfg,settings);execute([merger,cfg],root/f'{label}_{level}_{start}.log',deadline,2)
                        artifacts[str(result)]=sha(result);next_level.append(result)
                    current=next_level;level+=1
                return current[0]
            controls=out/'controls';controls.mkdir()
            def row(a,b,r):return dict(global_voltage_ids=[a,b],native_resistance_float_bits=struct.unpack('<I',struct.pack('<f',r))[0],
                native_resistance_milliohm_token=str(r),branch_kind='positive_native_resistor' if r else 'exact_zero_voltage_constraint')
            fixture=[row(1,2,25),row(2,3,50),row(1,3,0)]
            (controls/'branches.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in fixture))
            matrices=[]
            for threads in (1,4,8):
                root=controls/f'threads_{threads}';root.mkdir();cfg=root/'config.json'
                save(cfg,dict(branches=str(controls/'branches.jsonl'),voltage_nodes=4,threads=threads,
                     max_accumulator_entries=16,output=str(root/'runs'),deadline_uptime=deadline,expected_positive=2,expected_zero=1))
                execute([binary,cfg],root/'native.log',deadline,8)
                result=merge(sorted((root/'runs').glob('*.bin')),root,'matrix',True);matrices.append(result.read_bytes())
                actual={(a,b):int(value) for a,b,value,absolute,terms in map(json.loads,(root/'matrix.jsonl').read_text().splitlines())}
                assert actual=={(1,1):40,(1,2):-40,(2,2):60,(2,3):-20,(3,3):20}
            assert matrices[0]==matrices[1]==matrices[2]
            bad=[dict(fixture[0],native_resistance_milliohm_token='24'),*fixture[1:]]
            (controls/'bad.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in bad))
            cfg=controls/'bad.json';save(cfg,dict(branches=str(controls/'bad.jsonl'),voltage_nodes=4,threads=4,
                 max_accumulator_entries=16,output=str(controls/'bad_runs'),deadline_uptime=deadline,expected_positive=2,expected_zero=1))
            try:execute([binary,cfg],controls/'bad.log',deadline,8)
            except RuntimeError:pass
            else:raise ValueError('mismatched native float identity accepted')
            cfg=out/'config.json';save(cfg,dict(branches=str(branches),voltage_nodes=maps['voltage_nodes'],threads=8,
                 max_accumulator_entries=250000,output=str(scratch/'runs'),deadline_uptime=deadline,
                 expected_positive=native['results']['positive_native_resistors'],expected_zero=native['results']['exact_zero_voltage_branches']))
            status('assembling_every_native_positive_resistor')
            execute([binary,cfg],out/'native.log',deadline,16)
            summary=json.loads((out/'native.log').read_text());runs=sorted((scratch/'runs').glob('*.bin'))
            if len(runs)!=summary['sparse_runs'] or not runs:raise ValueError('complete native G runs required')
            artifacts.update({str(p):sha(p) for p in runs});status('reducing_native_core_G')
            matrix=merge(runs,scratch,'G')
            cfg=out/'matrix_audit.json';report=out/'matrix_audit.report.json'
            save(cfg,dict(matrix=str(matrix),node_count=maps['voltage_nodes'],threads=8,maximum_dense_bytes=16*1024**3,
                 deadline_uptime=deadline,scaled_charge_residual_limit=1e-12,report=str(report)))
            status('checking_every_native_core_G_row')
            execute([auditor,cfg],out/'matrix_audit.log',deadline,16)
            numeric=json.loads(report.read_text())
            if not numeric['necessary_checks_pass']:raise ValueError('native core G numerical structure failed')
            with ThreadPoolExecutor(max_workers=8) as pool:
                if list(pool.map(sha,paths))!=list(pins.values()):raise ValueError('native core G source changed')
            for p in [binary,matrix,report,out/'native.log',*[p for p in controls.rglob('*') if p.is_file()]]:artifacts[str(p)]=sha(p)
            save(out/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,native_core_G_matrix=str(matrix),
                 complete_native_positive_core_G_assembled=True,results=summary,numerical_matrix_structure=numeric,
                 exact_native_float_resistances_preserved=True,zero_R_constraints_not_replaced_by_resistors=True,
                 positive_zero_thread_and_mismatched_float_controls_pass=True,
                 source_projection_assessment_pending=True,full_spatial_G_matrix_assembled=False,
                 material_and_resistance_PVT_qualified=False,physical_RC_qualified=False,runtime_model_eligible=False,release_qualified=False))
            status('complete_native_positive_core_G_assembled',results=summary);print(json.dumps(summary))
    except BaseException as error:status('failed',reason=repr(error));raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('core','mapping','matrix-controls','merger-upgrade','output'):parser.add_argument('--'+name,type=Path,required=True)
    a=parser.parse_args();run(a.core,a.mapping,a.matrix_controls,a.merger_upgrade,a.output)
