"""Snapshot a live controller's PDK include closure from its mount namespace.

All static .include/.inc and file .lib references are traversed, including
inactive library sections. This conservative superset is not an execution trace
and cannot prove the runtime of a historical process that has already exited.
"""
import argparse,hashlib,json,os,posixpath,shlex
from pathlib import Path
from common_v3 import save,sha
from resources import identity


def dependencies(text,parent):
    result=[]
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith('*'):continue
        directive=line.split()[0].lower()
        if directive not in ('.include','.inc','.lib'):continue
        fields=shlex.split(line,comments=False)
        if len(fields)<2:raise ValueError('missing include argument')
        if directive=='.lib' and len(fields)==2:continue  # local section declaration
        path=fields[1]
        if '$' in path or '{' in path:raise ValueError('dynamic include cannot be statically pinned')
        result.append(posixpath.normpath(path if path.startswith('/') else posixpath.join(posixpath.dirname(parent),path)))
    return result


def closure(pid,library):
    pending=[library];hashes={};edges={}
    prefix='/opt/pdk/'
    while pending:
        logical=pending.pop()
        if logical in hashes:continue
        if not logical.startswith(prefix):raise ValueError('PDK include escaped supported namespace prefix')
        path=Path(f'/proc/{pid}/root')/logical.lstrip('/')
        data=path.read_bytes();hashes[logical]=hashlib.sha256(data).hexdigest()
        edges[logical]=dependencies(data.decode(),logical);pending.extend(edges[logical])
    return hashes,edges


def capture(native,library,image,output):
    if output.exists():raise FileExistsError(output)
    owner=json.loads((native/'owner.json').read_text());pid=owner['pid']
    if identity(pid)!=owner['birth']:raise ValueError('live controller identity required')
    logical=posixpath.normpath(library)
    image_digest=sha(image)
    before,edges=closure(pid,logical);after,_=closure(pid,logical)
    if before!=after or identity(pid)!=owner['birth']:raise ValueError('runtime files or controller identity changed during capture')
    if sha(image)!=image_digest:raise ValueError('declared image changed')
    save(output,dict(controller=owner,native=str(native),mount_namespace=os.readlink(f'/proc/{pid}/ns/mnt'),
        library=logical,PDK_static_include_superset_sha256=before,include_edges=edges,
        dependency_files=len(before),declared_container_image=str(image),declared_container_sha256=image_digest,
        input_sha256={str(native/'owner.json'):sha(native/'owner.json'),str(Path(__file__).resolve()):sha(Path(__file__))},
        capture_scope='live namespace observation; includes inactive sections; not a historical launch attestation',
        container_image_binding_proven=False,physical_models_qualified=False,release_ready=False))
    return len(before)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['native','image','output']:p.add_argument('--'+key,required=True,type=Path)
    p.add_argument('--library',required=True)
    a=p.parse_args();os.sched_setaffinity(0,{28})
    print('captured_PDK_dependency_files',capture(a.native.resolve(),a.library,a.image.resolve(),a.output.resolve()))
