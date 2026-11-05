"""Select small nonzero C rows for exact source proof; never authorize their removal."""
import argparse
from fractions import Fraction
import json
import os
from pathlib import Path
import time
from common import save,sha
from resources import identity,lease


def run(candidate,output):
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,
         cpu_slots=1,memory_GiB=2,automatic_identical_retry=False))
    def status(state,**kw):save(output/'status.json',dict(state=state,release_qualified=False,**kw))
    try:
        assessment=candidate/'assessment.json';a=json.loads(assessment.read_text())
        if a.get('conservative_C_stored_coefficient_derivative_certified') is not True:raise ValueError('certified candidate required')
        manifest=Path(a['logical_operator_manifest']);op=json.loads(manifest.read_text());rows=Path(op['correction_certificate']['path'])
        q=op['correction_certificate']['binary_quantum_exponent'];threshold=Fraction(1,100000000)/(Fraction(2)**q)
        paths=[assessment,manifest,rows,Path(__file__).resolve()]
        status('waiting_for_small_row_inventory_lease')
        with lease(1,2,deadline):
            pins={str(p):sha(p) for p in paths}
            if pins[str(rows)]!=op['correction_certificate']['sha256'] or pins[str(manifest)]!=a['artifacts'][str(manifest)]:
                raise ValueError('C row certificate lineage changed')
            status('inventorying_all_exact_C_row_norms')
            selected=[];isolated=0;seen=0;masked=0
            with rows.open() as stream:
                for line in stream:
                    if seen%10000==0 and time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('row inventory deadline')
                    r=json.loads(line)
                    if r['row']!=seen:raise ValueError('complete ordered C row certificate required')
                    seen+=1;l1=int(r['L1_integer']);diag=int(r['conservative_diagonal_integer'])
                    if l1<0:raise ValueError('nonnegative row norm required')
                    isolated+=l1==0;masked+=r['source_proven_zero_row']
                    if r['row']==0 or r['source_proven_zero_row'] or l1==0:continue
                    if l1<=threshold and abs(diag)<=threshold:
                        selected.append(dict(row=r['row'],diagonal_integer=str(diag),original_L1_integer=str(l1)))
            if seen!=op['node_count']:raise ValueError('C row inventory incomplete')
            if any(sha(Path(p))!=v for p,v in pins.items()):raise ValueError('C row inventory inputs changed')
            targets=output/'candidates.json';save(targets,dict(coefficient_quantum_exponent=q,selection_threshold_raw='1e-8',rows=selected,
                 selection_is_not_source_zero_proof=True,coefficient_change_authorized=False))
            save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(targets):sha(targets)},node_count=seen,
                 already_source_proven_zero_rows=masked,original_exact_zero_L1_rows=isolated,selected_rows=len(selected),
                 all_exact_row_norms_inventoried=True,threshold_only_selects_proof_work=True,
                 source_level_zero_row_certificate_complete=False,matrix_modified=False,
                 full_matrix_passivity_verified=False,physical_RC_qualified=False,release_qualified=False))
            status('small_C_row_inventory_complete',selected_rows=len(selected))
    except BaseException as error:
        status('stopped_without_promotion',reason=repr(error));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('candidate','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(a.candidate.resolve(),a.output.resolve())
