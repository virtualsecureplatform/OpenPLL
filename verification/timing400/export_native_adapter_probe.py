#!/usr/bin/env python3
"""Export unscaled captured equations for an integration-level adapter probe."""
import json
from pathlib import Path
import numpy as np
from scipy.sparse import load_npz
from compile_local_C_operators_v2 import digest,save
root=Path(__file__).resolve().parents[2]; base=root/'build/timing400/release_001'
folder=base/'native_adapter_probe_inputs_001'; folder.mkdir(exist_ok=False)
capture=base/'DCO_native_linear_system_capture_002'
A=load_npz(capture/'native_Jacobian.npz').tocsr(); A.sort_indices(); n=A.shape[0]
with (folder/'original_A.bin').open('xb') as handle:
    np.array([n,A.nnz],dtype='<i4').tofile(handle)
    np.asarray(A.indptr,dtype='<i4').tofile(handle); np.asarray(A.indices,dtype='<i4').tofile(handle)
    np.asarray(A.data,dtype='<f8').tofile(handle)
known=.1*(np.sin(np.arange(n)*.013)+np.cos(np.arange(n)*.027))
for label,rhs in [('known_solution',A@known),('native_Newton_RHS',np.load(capture/'native_RHS.npy'))]:
    np.asarray(rhs,dtype='<f8').tofile(folder/(label+'.bin'))
(folder/'dimensions.txt').write_text(str(n)+'\n')
inputs=[Path(__file__),capture/'assessment.json',capture/'native_Jacobian.npz',capture/'native_RHS.npy']
save(folder/'assessment.json',dict(original_native_equations_exported=True,states=n,numeric_nnz=int(A.nnz),
    input_sha256={str(p.resolve()):digest(p) for p in inputs},
    artifacts={str(p):digest(p) for p in folder.iterdir() if p.suffix=='.bin'},release_qualified=False))
