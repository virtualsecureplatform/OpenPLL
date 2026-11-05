"""Apply exact zero-R constraints and inspect the complete reduced spatial C."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import tempfile
import time
from common import save,sha
from compiled_charge import execute
from resources import identity,lease
from bind_projection_namespace import bind_namespace


def run(followup,mapping,zero_map,controls,matrix_controls,merger_upgrade,output):
    followup,mapping,zero_map,controls,matrix_controls,merger_upgrade,out=(p.resolve() for p in
        (followup,mapping,zero_map,controls,matrix_controls,merger_upgrade,output))
    out.mkdir(parents=True,exist_ok=False)
    owner=json.loads((followup/'owner.json').read_text());pid,birth=owner['pid'],owner['birth']
    if identity(pid)!=birth and not (followup/'assessment.json').exists():raise ValueError('live or successfully completed exact upstream required')
    receipts=[p/'assessment.json' for p in (mapping,zero_map,controls,matrix_controls,merger_upgrade)]
    maps,zeros,transform,check,upgrade=[json.loads(p.read_text()) for p in receipts]
    if not zeros['every_original_voltage_slot_independently_checked'] or not transform['ordered_zero_R_transform_controls_pass']:
        raise ValueError('controlled exact map and ordered transform required')
    if zeros['input_sha256'].get(str(receipts[0]))!=sha(receipts[0]) or not check['matrix_structure_controls_pass']:
        raise ValueError('map lineage or matrix controls missing')
    binary=controls/'collapse_zero_R_matrix';auditor=matrix_controls/'audit_sparse_matrix';merger=Path(upgrade['merger_binary'])
    voltage_map,aliases=(zero_map/name for name in ('voltage_map.bin','aliases.jsonl'))
    expected={str(binary):transform['artifacts'][str(binary)],str(auditor):check['artifacts'][str(auditor)],
        str(merger):upgrade['input_sha256'][str(merger)],
        **{str(p):zeros['artifacts'][str(p)] for p in (voltage_map,aliases)}}
    paths=[Path(__file__).resolve(),followup/'owner.json',*receipts,*map(Path,expected)]
    pins={str(p):sha(p) for p in paths}
    if any(pins[p]!=h for p,h in expected.items()):raise ValueError('controlled zero-R followup input changed')
    save(out/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),watched_pid=pid,watched_birth=birth,
         automatic_identical_retry=False,waiting_budget_s=172800,check_budget_s=43200))
    save(out/'input_manifest.json',dict(input_sha256=pins))
    def status(state,**extra):save(out/'status.json',dict(state=state,release_qualified=False,**extra))
    try:
        deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+172800
        status('waiting_for_exact_projection_reduction_followup')
        while identity(pid)==birth:
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('upstream wait budget expired')
            time.sleep(10)
        parent=followup/'assessment.json'
        if not parent.exists() or not json.loads(parent.read_text())['full_operator_projection_and_sparse_reduction_complete']:
            raise ValueError('complete upstream projection/reduction required')
        reduced=followup/'reduction/assessment.json';r=json.loads(reduced.read_text())
        projection=Path(r['source_projection']);producer=projection/'assessment.json';p=json.loads(producer.read_text())
        if not r['upper_triangle_sparse_matrix_reduced'] or not p['full_operator_coverage']:
            raise ValueError('full native operator coverage required')
        bridge_pins=bind_namespace(projection,mapping)
        if not (maps['source_projection']==str(projection) or bridge_pins) or r['global_voltage_nodes']!=zeros['results']['original_voltage_nodes']:
            raise ValueError('matching complete voltage namespace required')
        cfg=json.loads((mapping/'config.json').read_text())
        for key in ('R_nodes','floating_nodes'):
            name=str(Path(cfg[key]))
            if bridge_pins.get(name)!=maps['input_sha256'][name]:raise ValueError('final projection startup map identity differs')
        pins.update(bridge_pins)
        for name,h in pins.items():
            if sha(Path(name))!=h:raise ValueError('controlled zero-R source changed while waiting')
        matrix=Path(r['final_matrix']);scratch=Path(tempfile.mkdtemp(prefix='openpll-zero-R-C-',dir='/tmp'))
        (out/'native').symlink_to(scratch,target_is_directory=True)
        deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
        with lease(8,16,deadline):
            pins.update({str(f):sha(f) for f in (parent,reduced,producer,matrix)})
            if pins[str(matrix)]!=r['artifacts'][str(matrix)]:raise ValueError('full reduced C changed')
            config=out/'transform.json'
            save(config,dict(matrix=str(matrix),voltage_map=str(voltage_map),aliases=str(aliases),
                 max_accumulator_entries=1000000,output=str(scratch/'runs'),deadline_uptime=deadline))
            status('streaming_ordered_zero_R_matrix_transform')
            execute([binary,config],out/'transform.log',deadline,16)
            summary=json.loads((out/'transform.log').read_text());current=sorted((scratch/'runs').glob('*.bin'))
            if len(current)!=summary['sparse_runs']:raise ValueError('complete zero-R transform runs required')
            artifacts={str(f):sha(f) for f in current};level=0
            while len(current)>1:
                next_level=[]
                for start in range(0,len(current),128):
                    config=scratch/f'merge_{level}_{start}.json';result=scratch/f'merge_{level}_{start}.bin'
                    save(config,dict(inputs=list(map(str,current[start:start+128])),output=str(result),deadline_uptime=deadline))
                    execute([merger,config],scratch/f'merge_{level}_{start}.log',deadline,2)
                    artifacts[str(result)]=sha(result);next_level.append(result)
                current=next_level;level+=1
            final=current[0];config=out/'structure.json';report=out/'structure.report.json'
            save(config,dict(matrix=str(final),node_count=zeros['results']['constrained_voltage_nodes'],threads=8,
                 maximum_dense_bytes=16*1024**3,deadline_uptime=deadline,scaled_charge_residual_limit=1e-12,report=str(report)))
            status('auditing_every_zero_R_constrained_spatial_matrix_row')
            execute([auditor,config],out/'structure.log',deadline,16)
            with ThreadPoolExecutor(max_workers=8) as pool:
                if list(pool.map(sha,map(Path,pins)))!=list(pins.values()):raise ValueError('zero-R matrix audit input changed')
            artifacts[str(report)]=sha(report)
            save(out/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,constrained_matrix=str(final),
                 full_spatial_native_zero_R_constraint_transform_complete=True,transform_summary=summary,
                 necessary_matrix_checks=json.loads(report.read_text()),final_producer_node_maps_reconciled=True,
                 zero_R_constraints_applied=True,substrate_reference_fold_applied=False,
                 scalar_rounding_spatial_assignment_complete=False,full_matrix_passivity_verified=False,
                 physical_RC_qualified=False,runtime_model_eligible=False,release_qualified=False))
            status('zero_R_constrained_spatial_matrix_audit_complete')
    except BaseException as error:
        status('stopped_without_promotion',reason=repr(error));raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('followup','mapping','zero-map','controls','matrix-controls','merger-upgrade','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    a=parser.parse_args();run(a.followup,a.mapping,a.zero_map,a.controls,a.matrix_controls,a.merger_upgrade,a.output)
