#!/usr/bin/env python3
"""Export native GID wire-C metadata with an explicit non-C graph preservation mask."""
import json
from pathlib import Path
import numpy as np
from scipy.sparse import coo_matrix, load_npz
from compile_local_C_operators_v2 import digest, save

root=Path(__file__).resolve().parents[2]; base=root/'build/timing400/release_001'
out=base/'native_wire_preconditioner_metadata_001'; out.mkdir(exist_ok=False)
capture=base/'DCO_native_linear_system_capture_002'
folder=base/'DCO_local_C_matrix_nom_no_substrate_G_001'
proof=base/'native_solver_probe_checks_001/assessment.json'
assert json.loads(proof.read_text())['native_SDK_probe_passed']
variables=json.loads((capture/'native_variable_names.json').read_text())
lookup={name.upper():i for i,name in enumerate(variables)}; n=len(variables)
nodes=json.loads((folder/'nodes.json').read_text()); assert nodes[0]=='_dco_substrate_reference'
mapping=np.array([lookup['XDCO:XPHYSICAL:'+name.upper()] for name in nodes[1:]],dtype=np.int32)
index={name:int(mapping[i]) for i,name in enumerate(nodes[1:])}
C=(load_npz(folder/'C_native_units.npz')[1:,1:]*1e-18).tocoo()
selected=C.row!=C.col
C=coo_matrix((C.data[selected],(mapping[C.row[selected]],mapping[C.col[selected]])),shape=(n,n)).tocsr()
C.sum_duplicates(); C.eliminate_zeros(); C.sort_indices()
rows=np.repeat(np.arange(n,dtype=np.int64),np.diff(C.indptr)); keys=rows*n+C.indices
rfile=base/'DCO_domain_R_corners_002/nom_wire_R_unqualified.spice'
devices=base/'DCO_complete_domain_model_primitives_001/device_connections.json'
points=base/'DCO_direct_native_planes_and_boundaries_001/boundary_connections.json'
preserve=set(); rbranches=0
for line in rfile.open():
    f=line.split()
    if not f or f[0].startswith('*'): continue
    assert len(f)==4 and f[0].upper().startswith('R') and float(f[3])>0
    i,j=index[f[1]],index[f[2]]; preserve.update((i*n+j,j*n+i)); rbranches+=1
assert rbranches==166286
primitive=json.loads(devices.read_text())
for item in primitive.values():
    terminals=[index[name] for name in item['private_terminals']]
    preserve.update(i*n+j for i in terminals for j in terminals if i!=j)
allowed=np.array(sorted(preserve),dtype=np.int64)
positions=np.searchsorted(allowed,keys)
keep=(positions<len(allowed)) & (allowed[np.minimum(positions,len(allowed)-1)]==keys)
protected=np.ones(n,dtype=bool); protected[mapping]=False
for item in primitive.values():
    for name in item['private_terminals']: protected[index[name]]=True
for item in json.loads(points.read_text()): protected[index[item['private_node']]]=True
eligible=np.flatnonzero(~protected[rows] & ~protected[C.indices] & ~keep & (abs(C.data)>1e-22))
chosen=eligible[::max(1,len(eligible)//1024)][:1024]
assert len(chosen)==1024
sample=np.zeros(C.nnz,dtype=np.uint8); sample[chosen]=1
path=out/'wire_C.bin'
with path.open('xb') as handle:
    handle.write(b'OPLLCAP1')
    np.array([n,C.nnz],dtype='<i4').tofile(handle)
    np.asarray(C.indptr,dtype='<i4').tofile(handle)
    np.asarray(C.indices,dtype='<i4').tofile(handle)
    np.asarray(C.data,dtype='<f8').tofile(handle)
    np.asarray(keep,dtype=np.uint8).tofile(handle)
    sample.tofile(handle)
A=load_npz(capture/'native_Jacobian.npz').tocsr()
observed=np.asarray(A[rows[chosen],C.indices[chosen]]).reshape(-1)
ratios=observed/C.data[chosen]
assert np.max(abs(ratios/1e11-1))<1e-10
inputs=[Path(__file__),capture/'assessment.json',capture/'native_variable_names.json',
    capture/'native_Jacobian.npz',folder/'C_native_units.npz',folder/'nodes.json',rfile,devices,points,proof]
save(out/'assessment.json',dict(native_GID_metadata_exported=True,
    states=n,wire_C_offdiagonal_entries=int(C.nnz),
    R_or_device_C_pairs_preserved=int(np.count_nonzero(keep)),coefficient_samples=len(chosen),
    source_variable_names_sha256=digest(capture/'native_variable_names.json'),
    metadata_file=str(path),metadata_sha256=digest(path),
    preserves_all_wire_R_and_primitive_terminal_pair_slots=True,
    does_not_modify_fine_matrix=True,
    input_sha256={str(p.resolve()):digest(p) for p in inputs},
    runtime_mapping_identity_still_requires_candidate_names_export=True,
    release_qualified=False,adopted=False))
print(json.dumps(dict(states=n,C_entries=int(C.nnz),preserved=int(np.count_nonzero(keep)))))
