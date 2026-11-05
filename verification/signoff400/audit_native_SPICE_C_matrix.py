"""Audit complete serialized native C and diagnose its delta from the EXT trace."""
import argparse
import json
from pathlib import Path
import time
from common import save,sha
from compiled_charge import execute
from resources import lease


def run(output):
    output.mkdir(parents=True,exist_ok=False)
    base=Path('build/signoff400').resolve()
    assembly=base/'startup_timing_native_SPICE_C_matrix_001/assessment.json'
    fold=base/'startup_timing_ideal_substrate_references_001/assessment.json'
    controls=base/'matrix_structure_controls_001/assessment.json'
    comparison=base/'startup_timing_native_reference_delta_001/assessment.json'
    a,f,c,d=[json.loads(p.read_text()) for p in (assembly,fold,controls,comparison)]
    auditor=controls.parent/'audit_sparse_matrix';compare=comparison.parent/'compare_sparse_matrices'
    matrix=Path(a['matrix']);reference=Path(f['folded_matrices']['native_trace_delta'])
    names=base/'startup_timing_spatial_conductor_maps_001/native/net_names.jsonl'
    paths=[assembly,fold,controls,comparison,auditor,compare,matrix,reference,names,Path(__file__).resolve()]
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    with lease(8,8,deadline):
        pins={str(p):sha(p) for p in paths}
        if not a['full_serialized_native_SPICE_C_matrix_assembled'] or not c['matrix_structure_controls_pass']:raise ValueError('complete assembly and controlled structure auditor required')
        if a['input_sha256'][str(fold)]!=pins[str(fold)] or f['input_sha256'][str(names)]!=pins[str(names)] or a['input_sha256'][str(names)]!=pins[str(names)]:raise ValueError('ideal native namespace lineage mismatch')
        for proof,path in ((a,matrix),(f,reference),(c,auditor),(d,compare)):
            if proof['artifacts'][str(path)]!=pins[str(path)]:raise ValueError('audited artifact hash mismatch')
        nodes=f['ideal_native_conductor_nets']
        cfg=output/'structure.json';report=output/'structure.report.json'
        save(cfg,dict(matrix=str(matrix),node_count=nodes,threads=8,maximum_dense_bytes=8*1024**3,
             deadline_uptime=deadline,scaled_charge_residual_limit=1e-12,report=str(report)))
        execute([auditor,cfg],output/'structure.log',deadline,8)
        cfg=output/'delta.json';delta=output/'delta.report.json'
        save(cfg,dict(left=str(reference),right=str(matrix),node_count=nodes,absolute_tolerance=1e-8,
             relative_tolerance=2e-12,require_match=False,deadline_uptime=deadline,report=str(delta)))
        execute([compare,cfg],output/'delta.log',deadline,8)
        if any(sha(p)!=pins[str(p)] for p in paths):raise ValueError('native C audit input changed')
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in (report,delta)},
             all_serialized_native_SPICE_C_rows_and_2x2_minors_checked=True,
             ideal_substrate_and_original_conductor_name_lineage_reconciled=True,
             necessary_matrix_checks=json.loads(report.read_text()),native_EXT_to_SPICE_delta_diagnostic=json.loads(delta.read_text()),
             diagnostic_tolerances_are_not_serialization_acceptance_bounds=True,
             full_SPICE_matrix_equivalence_verified=False,full_matrix_passivity_verified=False,
             physical_RC_qualified=False,release_qualified=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);run(p.parse_args().output.resolve())
