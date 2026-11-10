"""Measure exact symmetry of a completed native matrix without altering it."""
import json,time
from pathlib import Path
import numpy as np
from common_v3 import ROOT,save,sha,verify
from resources import lease,identity
from map_zero_RC_rows_1801 import arrays

def run():
    base=ROOT/'build/signoff400';source=base/'selected_zero_C_backend_CSC_capture_1813';receipt=source/'assessment.json';r=json.loads(receipt.read_text());verify(r['artifacts'])
    o=json.loads((source/'native.process.json').read_text())
    if identity(o['pid'])==o['birth'] or not r['native_diagnostic_completed']:raise ValueError('completed exact capture required')
    out=base/'selected_RC_matrix_symmetry_1820';out.mkdir(exist_ok=False)
    with lease(1,6,time.clock_gettime(time.CLOCK_BOOTTIME)+120):
        n,ap,ai,ax=arrays(source/'matrix')
        col=np.repeat(np.arange(n,dtype=np.int64),np.diff(ap));keys=col*n+ai
        if not np.all(np.diff(keys)>0):raise ValueError('strictly sorted unique CSC required')
        transposed=ai.astype(np.int64)*n+col;order=np.argsort(transposed);other=transposed[order]
        matching=np.array_equal(keys,other)
        if matching:
            delta=ax-ax[order];asym=int(np.count_nonzero(delta));maximum=float(np.max(np.abs(delta)))
        else:asym=None;maximum=None
        report=dict(rows=n,stored_entries=len(ai),pattern_exactly_symmetric=matching,numerically_asymmetric_entries=asym,maximum_absolute_asymmetry=maximum,nonzero_diagonal=int(np.count_nonzero(ax[ai==col])),matrix_modified=False)
        save(out/'assessment.json',dict(input_sha256={str(p):sha(p)for p in [receipt,Path(__file__).resolve(),Path(__file__).with_name('map_zero_RC_rows_1801.py')]},**report,release_ready=False))
if __name__=='__main__':run()
