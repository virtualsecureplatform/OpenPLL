"""Inspect only a normally completed exact native CSC capture; do not modify it."""
import json,time,struct
from pathlib import Path
import numpy as np
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease

def run():
    base=ROOT/'build/signoff400';source=base/'selected_zero_C_backend_CSC_capture_1813';receipt=source/'assessment.json';r=json.loads(receipt.read_text())
    process=json.loads((source/'native.process.json').read_text())
    if identity(process['pid'])==process['birth'] or not r['native_diagnostic_completed'] or r['simulation_solved']:raise ValueError('completed matrix-only diagnostic required')
    verify(r['input_sha256']);verify(r['artifacts']);pins={str(p):sha(p)for p in [receipt,Path(__file__).resolve()]}
    out=base/'selected_zero_C_backend_CSC_assessment_1814';out.mkdir(exist_ok=False)
    with lease(1,6,time.clock_gettime(time.CLOCK_BOOTTIME)+600):
        p=source/'matrix';magic,n,m,nnz=struct.unpack('=4Q',(p/'header.u64').read_bytes())
        if magic!=0x4f504c4c43534331 or n!=m:raise ValueError('exact square native CSC required')
        ap=np.fromfile(p/'columns.i32',dtype=np.int32);ai=np.fromfile(p/'rows.i32',dtype=np.int32);ax=np.fromfile(p/'values.f64',dtype=np.float64)
        if len(ap)!=m+1 or len(ai)!=nnz or len(ax)!=nnz or ap[0]!=0 or ap[-1]!=nnz or np.any(np.diff(ap)<0) or np.any(ai<0)or np.any(ai>=n)or not np.all(np.isfinite(ax)):raise ValueError('invalid exact CSC')
        cols=np.repeat(np.arange(m,dtype=np.int32),np.diff(ap));nz=ax!=0
        row_degree=np.bincount(ai,minlength=n);column_degree=np.diff(ap);numeric_rows=np.bincount(ai[nz],minlength=n);numeric_cols=np.bincount(cols[nz],minlength=m)
        diag=ai==cols;diag_values=np.zeros(n);diag_values[ai[diag]]=ax[diag]
        def population(a):
            top=np.argsort(a)[-10:][::-1]
            return dict(zero=int(np.sum(a==0)),maximum=int(a.max()),top_indices=[int(x)for x in top],top_degrees=[int(a[x])for x in top],percentiles={str(q):float(np.percentile(a,q))for q in [50,90,99,99.9]})
        report=dict(rows=n,columns=m,stored_entries=nnz,exact_zero_entries=int(np.sum(~nz)),nonzero_entries=int(np.sum(nz)),structural_rows=population(row_degree),structural_columns=population(column_degree),nonzero_rows=population(numeric_rows),nonzero_columns=population(numeric_cols),diagonal_stored=int(np.sum(diag)),diagonal_exact_zero=int(np.sum(diag_values==0)),negative_diagonal=int(np.sum(diag_values<0)),minimum_value=float(ax.min()),maximum_value=float(ax.max()),matrix_modified=False,simulation_solved=False)
        save(out/'report.json',report);verify(pins)
        save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(out/'report.json'):sha(out/'report.json')},completed_exact_native_CSC_inspected=True,RC_backend_qualified=False,release_ready=False))
if __name__=='__main__':run()
