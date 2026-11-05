"""Combine exact zero-row proof leaves bound to one extraction and zero-R map."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import time
from common import ROOT,save,sha
from resources import identity,lease


def add_pins(destination, additions):
    for path,digest in additions.items():
        if path in destination and destination[path]!=digest:
            raise ValueError('proof leaves disagree about input identity: '+path)
        destination[path]=digest


def leaf_rows(proof,report,targets):
    if (proof.get('source_level_zero_row_certificate_complete') is not True
            or report.get('all_target_rows_exactly_zero') is not True
            or report.get('nonzero_symbolic_coefficients')!=0):
        raise ValueError('complete exact source-zero row proof required')
    declared={}
    for row in targets['negative_nodes']:
        i=row['row']
        if type(i) is not int or i<=0 or i in declared or not row['original_voltage_nodes']:
            raise ValueError('unique non-reference physical row targets required')
        identities=[(n['node'],n['name']) for n in row['original_voltage_nodes']]
        if (len(set(identities))!=len(identities) or any(type(i) is not int or i<=0 or not isinstance(name,str) or not name for i,name in identities)):
            raise ValueError('invalid original voltage identities')
        declared[i]=row
    observed=report['rows'];observed_ids=[row['row'] for row in observed]
    if (not declared or len(observed_ids)!=len(set(observed_ids)) or set(observed_ids)!=set(declared)
            or not all(row.get('entire_row_exactly_zero') is True and row.get('nonzero_symbolic_coefficients')==0 for row in observed)):
        raise ValueError('zero-row report/target coverage differs')
    return declared


def run(output,leaves):
    output.mkdir(parents=True,exist_ok=False)
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,
         cpu_slots=16,memory_GiB=4,automatic_identical_retry=False))
    expected={};rows={};row_proofs={};namespace=None;projection=None;exponent=None
    try:
        for leaf in leaves:
            proof_path=leaf/'assessment.json'
            if not proof_path.exists():
                parent=json.loads((leaf/'owner.json').read_text())
                while not proof_path.exists():
                    if identity(parent['pid'])!=parent['birth'] or time.clock_gettime(time.CLOCK_BOOTTIME)>=min(deadline,parent.get('deadline_uptime',deadline)+60):
                        raise RuntimeError('proof leaf terminal without complete exact certificate')
                    save(output/'status.json',dict(state='waiting_for_exact_proof_leaf',producer_pid=parent['pid'],release_qualified=False));time.sleep(2)
            proof=json.loads(proof_path.read_text());cfg=leaf/'config.json';report_path=leaf/'report.json'
            config=json.loads(cfg.read_text());report=json.loads(report_path.read_text());targets_path=Path(config['targets'])
            targets=json.loads(targets_path.read_text());current=leaf_rows(proof,report,targets)
            for path in (cfg,report_path):
                if sha(path)!=proof['artifacts'][str(path)]:raise ValueError('proof leaf artifact changed')
            if sha(targets_path)!=proof['artifacts'].get(str(targets_path),proof['input_sha256'].get(str(targets_path))):
                raise ValueError('proof leaf target identities changed')
            compact=Path(config['voltage_map']);compact_identity=(str(compact),proof['input_sha256'][str(compact)])
            # Both original leaves and composites must pin this exact completed source.
            source=ROOT/'build/signoff400/startup_timing_full_spatial_projection_002/assessment.json'
            source_identity=(str(source),proof['input_sha256'][str(source)])
            if namespace is None:namespace,projection,exponent=compact_identity,source_identity,targets['energy_binary_quantum_exponent']
            if compact_identity!=namespace or source_identity!=projection:
                raise ValueError('zero-row proofs belong to different extraction namespaces')
            if targets['energy_binary_quantum_exponent']!=exponent:raise ValueError('zero-row energy quantum differs')
            for i,row in current.items():
                if i in rows:
                    old={(n['node'],n['name']) for n in rows[i]['original_voltage_nodes']}
                    new={(n['node'],n['name']) for n in row['original_voltage_nodes']}
                    if old!=new:raise ValueError('duplicate proof rows disagree about physical aliases')
                else:rows[i]=row
                row_proofs.setdefault(i,[]).append(dict(path=str(proof_path),sha256=sha(proof_path)))
            add_pins(expected,proof['input_sha256'])
            add_pins(expected,{str(path):sha(path) for path in (proof_path,cfg,report_path,targets_path)})
        if not leaves:raise ValueError('at least one exact proof leaf required')
        add_pins(expected,{str(Path(__file__).resolve()):sha(Path(__file__).resolve())})
        with lease(16,4,deadline):
            save(output/'status.json',dict(state='verifying_all_combined_proof_inputs',release_qualified=False))
            paths=list(expected)
            with ThreadPoolExecutor(max_workers=16) as pool:actual=dict(zip(paths,pool.map(sha,paths)))
            if actual!=expected:raise ValueError('combined proof input changed')
            targets_path=output/'targets.json';config_path=output/'config.json';report_path=output/'report.json'
            save(targets_path,dict(schema_version=1,negative_nodes=[rows[i] for i in sorted(rows)],
                 energy_binary_quantum_exponent=exponent,source_projection=projection[0],
                 physical_RC_qualified=False,release_qualified=False))
            save(config_path,dict(targets=str(targets_path),voltage_map=namespace[0],source_projection=projection[0]))
            result=dict(all_target_rows_exactly_zero=True,nonzero_symbolic_coefficients=0,target_rows=len(rows),
                 rows=[dict(row=i,entire_row_exactly_zero=True,nonzero_symbolic_coefficients=0,proof_leaves=row_proofs[i]) for i in sorted(rows)],
                 full_matrix_passivity_verified=False,physical_RC_qualified=False,release_qualified=False)
            save(report_path,result)
            save(output/'assessment.json',dict(input_sha256=expected,
                 artifacts={str(path):sha(path) for path in (targets_path,config_path,report_path)},results=result,
                 source_level_zero_row_certificate_complete=True,all_target_C_rows_exactly_zero=True,
                 complete_target_C_symbolic_row_expressions_assembled=True,proof_composition='union of exact source-bound zero-row leaves',
                 numerical_coefficient_threshold_used=False,matrix_modified=False,full_matrix_passivity_verified=False,
                 physical_RC_qualified=False,release_qualified=False))
            save(output/'status.json',dict(state='combined_source_zero_row_proof_complete',rows=len(rows),release_qualified=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_promotion',reason=repr(error),release_qualified=False));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path)
    p.add_argument('--leaf',action='append',required=True,type=Path);a=p.parse_args();run(a.output.resolve(),[p.resolve() for p in a.leaf])
