"""Prepare all floating charge rows after the exact constrained spatial C seals."""
from concurrent.futures import ThreadPoolExecutor
import argparse
import json
import os
from pathlib import Path
import tempfile
import time
from common import save,sha
from compiled_charge import execute
from resources import identity,lease


def run(output):
    output.mkdir(parents=True,exist_ok=False);base=Path('build/signoff400').resolve()
    upstream=base/'startup_timing_spatial_zero_R_followup_001';owner=upstream/'owner.json';o=json.loads(owner.read_text());pid,birth=o['pid'],o['birth']
    if identity(pid)!=birth:raise ValueError('exact upstream zero-R C process must be live at registration')
    controls=base/'floating_charge_row_controls_001/assessment.json';roles=base/'startup_timing_G_component_roles_001/assessment.json'
    components=base/'startup_timing_G_components_001/assessment.json';zero=base/'startup_timing_zero_R_voltage_map_002/assessment.json'
    conductors=base/'startup_timing_spatial_conductor_maps_001/assessment.json'
    c,r,g=[json.loads(p.read_text()) for p in (controls,roles,components)]
    projector=controls.parent/'project_floating_charge_rows';merger=controls.parent/'merge_charge_rows'
    role_map=roles.parent/'component_roles.bin';component_map=components.parent/'constrained_voltage_conductors.bin'
    paths=[owner,controls,roles,components,zero,conductors,projector,merger,role_map,component_map,Path(__file__).resolve()]
    pins={str(p):sha(p) for p in paths}
    if not c['rectangular_floating_charge_projection_controls_pass'] or not r['every_graph_component_classified_against_all_devices_ports_and_floating_basis']:
        raise ValueError('controlled projection and full component classification required')
    for proof,path in ((c,projector),(c,merger),(r,role_map),(g,component_map)):
        if proof['artifacts'][str(path)]!=pins[str(path)]:raise ValueError('charge transform artifact changed')
    if r['input_sha256'][str(components)]!=pins[str(components)]:raise ValueError('role/component lineage differs')
    for proof in (zero,conductors):
        if g['input_sha256'][str(proof)]!=pins[str(proof)]:raise ValueError('component voltage namespace differs')
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),watched_pid=pid,watched_birth=birth,
         automatic_identical_retry=False,waiting_budget_s=86400,check_budget_s=43200))
    save(output/'input_manifest.json',dict(input_sha256=pins))
    def status(state,**more):save(output/'status.json',dict(state=state,release_qualified=False,**more))
    try:
        deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+86400;status('waiting_for_exact_zero_R_constrained_C')
        while identity(pid)==birth:
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('upstream wait budget')
            time.sleep(10)
        parent=upstream/'assessment.json';p=json.loads(parent.read_text())
        if not p['full_spatial_native_zero_R_constraint_transform_complete'] or not p['final_producer_node_maps_reconciled']:
            raise ValueError('complete constrained spatial C and final map reconciliation required')
        for proof in (zero,conductors):
            if p['input_sha256'][str(proof)]!=pins[str(proof)]:raise ValueError('final C and G component maps differ')
        if p['necessary_matrix_checks']['node_count']!=g['results']['constrained_voltage_nodes']:raise ValueError('charge voltage dimension mismatch')
        matrix=Path(p['constrained_matrix']);scratch=Path(tempfile.mkdtemp(prefix='openpll-floating-charge-rows-',dir='/tmp'))
        (output/'native').symlink_to(scratch,target_is_directory=True);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
        with lease(8,8,deadline):
            for name,digest in pins.items():
                if sha(Path(name))!=digest:raise ValueError('charge source changed while waiting')
            pins[str(parent)]=sha(parent);pins[str(matrix)]=sha(matrix)
            if pins[str(matrix)]!=p['artifacts'][str(matrix)]:raise ValueError('final spatial C changed')
            cfg=output/'project.json';save(cfg,dict(matrix=str(matrix),components=str(component_map),roles=str(role_map),threads=8,
                 max_accumulator_entries=500000,deadline_uptime=deadline,output=str(scratch/'runs')))
            status('projecting_every_floating_charge_row')
            execute([projector,cfg],output/'project.log',deadline,8);summary=json.loads((output/'project.log').read_text())
            current=sorted((scratch/'runs').glob('part_*_run_*.bin'));row_components=scratch/'runs/row_components.bin'
            if len(current)!=summary['sparse_runs'] or summary['charge_rows']!=r['results']['all_components_without_device_or_port']:
                raise ValueError('full floating charge row coverage')
            artifacts={str(f):sha(f) for f in [*current,row_components]};level=0;final_report=None
            while len(current)>1:
                jobs=[];following=[]
                for start in range(0,len(current),64):
                    cfg=scratch/f'merge_{level}_{start}.json';result=scratch/f'merge_{level}_{start}.bin';log=scratch/f'merge_{level}_{start}.log'
                    save(cfg,dict(inputs=list(map(str,current[start:start+64])),output=str(result),deadline_uptime=deadline));jobs.append((cfg,log));following.append(result)
                status('reducing_floating_charge_rows',level=level,input_runs=len(current))
                with ThreadPoolExecutor(max_workers=8) as pool:list(pool.map(lambda job:execute([merger,job[0]],job[1],deadline,2),jobs))
                for result in following:artifacts[str(result)]=sha(result)
                final_report=json.loads(jobs[0][1].read_text()) if len(following)==1 else None
                current=following;level+=1
            if final_report is None:
                cfg=scratch/'final_audit.json';result=scratch/'final_audited.bin';log=scratch/'final_audit.log'
                save(cfg,dict(inputs=list(map(str,current)),output=str(result),deadline_uptime=deadline));execute([merger,cfg],log,deadline,2)
                current=[result];final_report=json.loads(log.read_text());artifacts[str(result)]=sha(result)
            with ThreadPoolExecutor(max_workers=8) as pool:
                if list(pool.map(sha,map(Path,pins)))!=list(pins.values()):raise ValueError('floating charge input changed during projection')
            save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,charge_matrix=str(current[0]),row_components=str(row_components),
                 all_floating_conductor_linear_charge_rows_prepared=True,projection_summary=summary,rectangular_matrix_report=final_report,
                 global_voltage_gauge_within_limit=final_report['maximum_scaled_global_voltage_gauge_residual']<=1e-12,
                 charge_operator_definition='P_unattached^T C with every constrained voltage column retained',
                 raw_capacitance_unit_SI_farads='1e-18',initial_charge_values_assigned=False,
                 native_solver_charge_constraints_implemented=False,scalar_rounding_and_junction_allocation_qualified=False,
                 full_matrix_passivity_verified=False,physical_RC_qualified=False,runtime_model_eligible=False,release_qualified=False))
            status('all_floating_linear_charge_rows_prepared')
    except BaseException as error:
        status('stopped_without_promotion',reason=repr(error));raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);run(p.parse_args().output.resolve())
