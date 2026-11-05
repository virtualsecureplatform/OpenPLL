#!/usr/bin/env python3
"""Audit a completed isolated relink whose final manifest included its output."""
import hashlib
import json
from pathlib import Path
from compile_local_C_operators_v2 import digest,save
from record_qualification_progress_045 import process

root=Path(__file__).resolve().parents[2];base=root/'build/timing400/release_001'
out=base/'wire_preconditioned_Xyce_bounded_reuse_001'
assert not process(json.loads((out/'owner.json').read_text())['runner_pid'])['live']
failed=json.loads((out/'failure_receipt.json').read_text())
assert failed['error_type']=='AssertionError' and failed['message']==str(out/'libxyce.a')
stages=json.loads((out/'stage_receipts.json').read_text())
assert [s['stage'] for s in stages]==['compile','replace_archive_member','link']
assert all(s['exit_code']==0 for s in stages)
pins=json.loads((out/'input_manifest.json').read_text())['input_sha256']
# The manifest before linking is authoritative for original read-only inputs.
assert str(out/'libxyce.a') in pins
old_output_sha=pins.pop(str(out/'libxyce.a'))
for p,sha in pins.items():assert digest(Path(p))==sha,p
old=base/'wire_preconditioned_Xyce_001/build/src/libxyce.a'
assert digest(old)==old_output_sha

def members(path):
    data=path.read_bytes();assert data[:8]==b'!<arch>\n';pos=8;raw=[];names=b''
    while pos<len(data):
        header=data[pos:pos+60];assert len(header)==60 and header[-2:]==b'`\n'
        name=header[:16].decode().strip();size=int(header[48:58]);pos+=60
        body=data[pos:pos+size];assert len(body)==size;pos+=size+(size%2)
        if name=='//':names=body
        raw.append((name,body))
    assert pos==len(data)
    result={}
    for name,body in raw:
        if name in ('/','//'):continue
        if name.startswith('/'):
            off=int(name[1:]);name=names[off:names.index(b'/\n',off)].decode()
        else:name=name.rstrip('/')
        assert name not in result,name
        result[name]=hashlib.sha256(body).hexdigest()
    return result
original,current=members(old),members(out/'libxyce.a')
assert original.keys()==current.keys()
changed=[name for name in original if original[name]!=current[name]]
assert changed==['N_LAS_AmesosSolver.C.o'],changed
assert current[changed[0]]==digest(out/changed[0])
header=root/'verification/timing400/native_wire_preconditioner/OpenPLL_WirePreconditioner_warm_reuse_bounded.h'
assert digest(header)==digest(out/header.name)
source=base/'wire_preconditioned_Xyce_001/source/src/LinearAlgebraServicesPKG/N_LAS_AmesosSolver.C'
expected=source.read_text().replace('OpenPLL_WirePreconditioner_v2.h',header.name).replace('OpenPLLWirePC::solve','OpenPLLWireBoundedReusePC::solve')
assert (out/'N_LAS_AmesosSolver.C').read_text()==expected
binary=out/'Xyce'
with binary.open('rb') as stream:assert stream.read(4)==b'\x7fELF'
for p in (Path(__file__).resolve(),out/'failure_receipt.json',out/'stage_receipts.json',out/'N_LAS_AmesosSolver.C',out/header.name,out/'libxyce.a',out/'N_LAS_AmesosSolver.C.o'):
    pins[str(p)]=digest(p)
save(out/'recovered_build_assessment.json',dict(experimental_build_completed=True,binary=str(binary),binary_sha256=digest(binary),
    input_sha256=pins,changed_archive_members=changed,unchanged_archive_members=len(original)-1,
    original_failure_preserved=True,build_rerun=False,live_binary_and_source_unchanged=True,
    native_controls_passed=False,release_qualified=False,adopted=False))
print('Isolated build audited:',len(original),'members; one intended replacement')
