"""Audit every reduced spatial coefficient after exact upstream completion."""
import argparse
import json
import os
from pathlib import Path
import time
from common import save, sha
from compiled_charge import execute
from resources import identity, lease


def run(followup, controls, output):
    followup, controls, out = (p.resolve() for p in (followup, controls, output))
    out.mkdir(parents=True, exist_ok=False)
    owner = json.loads((followup/'owner.json').read_text())
    process, birth = owner['pid'], owner['birth']
    if identity(process)!=birth:
        raise ValueError('exact upstream followup must be live when watcher starts')
    proof=controls/'assessment.json'
    control=json.loads(proof.read_text())
    if not control['matrix_structure_controls_pass'] or not control['necessary_checks_explicitly_insufficient_for_PSD']:
        raise ValueError('controlled necessary-only matrix checks required')
    binary=controls/'audit_sparse_matrix'
    if sha(binary)!=control['artifacts'][str(binary)]:
        raise ValueError('controlled matrix auditor changed')
    paths=[Path(__file__).resolve(),followup/'owner.json',proof,binary]
    pins={str(p):sha(p) for p in paths}
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+86400
    save(out/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),
         watched_reduction_followup_pid=process,watched_reduction_followup_birth=birth,
         automatic_identical_retry=False,waiting_budget_s=86400,check_budget_s=43200))
    save(out/'input_manifest.json',dict(input_sha256=pins))
    def status(state,**extra):
        save(out/'status.json',dict(state=state,release_qualified=False,**extra))
    try:
        status('waiting_for_exact_projection_reduction_followup',pid=process,birth=birth)
        while identity(process)==birth:
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:
                raise TimeoutError('upstream bounded wait expired')
            time.sleep(10)
        parent=followup/'assessment.json'
        if not parent.exists() or not json.loads(parent.read_text())['full_operator_projection_and_sparse_reduction_complete']:
            raise ValueError('upstream projection/reduction did not publish success')
        receipt=followup/'reduction/assessment.json'
        reduced=json.loads(receipt.read_text())
        if not reduced['upper_triangle_sparse_matrix_reduced']:
            raise ValueError('complete reduced spatial matrix required')
        matrix=Path(reduced['final_matrix'])
        for p,h in pins.items():
            if sha(Path(p))!=h:
                raise ValueError('matrix structure source changed while waiting')
        deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
        with lease(8,16,deadline):
            status('hashing_complete_spatial_matrix')
            pins.update({str(p):sha(p) for p in (parent,receipt,matrix)})
            if pins[str(matrix)]!=reduced['artifacts'][str(matrix)]:
                raise ValueError('reduced spatial matrix changed')
            cfg,report=out/'audit.json',out/'structure.json'
            save(cfg,dict(matrix=str(matrix),node_count=reduced['global_voltage_nodes'],threads=8,
                 maximum_dense_bytes=16*1024**3,deadline_uptime=deadline,
                 scaled_charge_residual_limit=1e-12,report=str(report)))
            status('checking_every_spatial_row_and_nonzero_two_by_two_minor')
            execute([binary,cfg],out/'audit.log',deadline,16)
            result=json.loads(report.read_text())
            if any(sha(Path(p))!=h for p,h in pins.items()):
                raise ValueError('spatial structure input changed during audit')
            save(out/'assessment.json',dict(input_sha256=pins,
                 artifacts={str(p):sha(p) for p in (cfg,report,out/'audit.log')},
                 complete_unconstrained_spatial_matrix_structure_audit=True,
                 unconstrained_necessary_checks_pass=result['necessary_checks_pass'],results=result,
                 scope='unfolded unconstrained FEM coefficient matrix before zero-R and actual substrate constraints',
                 zero_R_and_substrate_constraints_applied=False,
                 negative_modes_require_constraint_compatibility_check=True,
                 full_matrix_passivity_verified=False,global_passivity_qualified=False,
                 physical_RC_qualified=False,release_qualified=False))
            status('unconstrained_spatial_structure_audit_complete',necessary_checks_pass=result['necessary_checks_pass'])
    except BaseException as error:
        status('stopped_without_promotion',reason=repr(error))
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('followup','controls','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    run(args.followup,args.controls,args.output)
