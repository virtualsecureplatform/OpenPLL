"""Observe PDK and executable identity of live native phase probes.

This captures a static include superset in each live namespace. It does not
retrospectively attest launch contents or prove a declared image was mounted.
"""
import argparse,json,os
from pathlib import Path
from common_v3 import save,sha,verify
from resources import identity
from capture_selected_native_runtime import closure


def run(cases,reference,image,output):
    if output.exists():raise FileExistsError(output)
    r=json.loads(reference.read_text());verify(r['input_sha256'])
    pins={str(p):sha(p) for p in [reference,Path(__file__).resolve(),Path(__file__).with_name('capture_selected_native_runtime.py')]}
    image_digest=sha(image);records=[]
    for case in cases:
        owner_path=case/'owner.json';process_path=case/'native.process.json';manifest_path=case/'manifest.json'
        owner=json.loads(owner_path.read_text());process=json.loads(process_path.read_text());m=json.loads(manifest_path.read_text())
        for item in [owner,process]:
            if identity(item['pid'])!=item['birth']:raise ValueError('live controller and native identities required')
        ns=os.readlink(f'/proc/{owner["pid"]}/ns/mnt')
        if os.readlink(f'/proc/{process["pid"]}/ns/mnt')!=ns:raise ValueError('native worker mount namespace differs from controller')
        before,edges=closure(process['pid'],r['library']);after,_=closure(process['pid'],r['library'])
        binaries=[p for p in m['input_sha256'] if p.endswith('/Xyce')]
        if len(binaries)!=1:raise ValueError('one pinned native executable required')
        executable_digest=sha(Path(f'/proc/{process["pid"]}/exe'))
        if before!=after:raise ValueError('PDK dependency bytes changed during capture')
        for item in [owner,process]:
            if identity(item['pid'])!=item['birth']:raise ValueError('native/controller identity changed during capture')
        for p in [owner_path,process_path,manifest_path]:pins[str(p)]=sha(p)
        records.append(dict(native=str(case),controller=owner,process=process,mount_namespace=ns,
            PDK_static_include_superset_sha256=before,include_edges=edges,dependency_files=len(before),
            matches_reference_PDK=before==r['PDK_static_include_superset_sha256'],
            live_executable_sha256=executable_digest,matches_pinned_executable=executable_digest==m['input_sha256'][binaries[0]]))
    verify(pins)
    save(output,dict(input_sha256=pins,declared_image=str(image),declared_image_sha256=image_digest,
        declared_image_matches_reference=image_digest==r['declared_container_sha256'],records=records,
        all_live_dependencies_match_reference=all(v['matches_reference_PDK'] and v['matches_pinned_executable'] for v in records),
        capture_scope='live namespace and executable observation; static include superset; not historical launch attestation',
        container_image_binding_proven=False,physical_models_qualified=False,release_ready=False))
    print('captured_native_cases',len(records),'dependency_files_per_case',[v['dependency_files'] for v in records])


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--case',action='append',type=Path,required=True)
    for n in ['reference','image','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();os.sched_setaffinity(0,{31});run([p.resolve() for p in a.case],a.reference.resolve(),a.image.resolve(),a.output.resolve())
