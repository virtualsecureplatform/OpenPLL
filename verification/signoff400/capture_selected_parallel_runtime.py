"""Observe live MPI launchers, rank executables, affinities and PDK bytes.

Read only the three relevant MPI/thread environment values. This records the
live namespace, not historical launch contents or container-image attestation.
"""
import argparse,json,os
from pathlib import Path
from common_v3 import save,sha,verify
from resources import identity
from capture_selected_native_runtime import closure


def workers(deck,binary_sha):
    records=[]
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():continue
        try:
            args=(proc/'cmdline').read_bytes().split(b'\0')
            if str(deck).encode() not in args:continue
            birth=identity(int(proc.name))
            if birth is None or sha(proc/'exe')!=binary_sha:continue
            wanted={'OMPI_COMM_WORLD_RANK','OMPI_COMM_WORLD_SIZE','OMP_NUM_THREADS'}
            env={}
            for entry in (proc/'environ').read_bytes().split(b'\0'):
                key,sep,value=entry.partition(b'=')
                if sep and key.decode(errors='replace') in wanted:env[key.decode()]=value.decode()
            records.append(dict(pid=int(proc.name),birth=birth,environment=env,CPU_affinity=sorted(os.sched_getaffinity(int(proc.name))),
                executable_sha256=binary_sha,mount_namespace=os.readlink(proc/'ns/mnt')))
        except (FileNotFoundError,ProcessLookupError,PermissionError):continue
    return sorted(records,key=lambda r:int(r['environment'].get('OMPI_COMM_WORLD_RANK','-1')))


def run(natives,reference,image,output):
    if output.exists():raise FileExistsError(output)
    r=json.loads(reference.read_text());verify(r['input_sha256']);records=[]
    pins={str(p):sha(p) for p in [reference,Path(__file__).resolve(),Path(__file__).with_name('capture_selected_native_runtime.py')]}
    image_sha=sha(image)
    for native in natives:
        op,pp,mp=[native/n for n in ['owner.json','native.process.json','manifest.json']]
        owner,process,m=[json.loads(p.read_text()) for p in [op,pp,mp]]
        for item in [owner,process]:
            if identity(item['pid'])!=item['birth']:raise ValueError('live controller/launcher identities required')
        expected=m.get('CPUs') or m.get('MPI_CPUs');count=m.get('MPI_ranks')
        if not expected or count!=len(expected):raise ValueError('explicit MPI CPU inventory required')
        binary=[p for p in m['input_sha256'] if p.endswith('/Xyce')]
        if len(binary)!=1:raise ValueError('unique pinned native executable required')
        found=workers(native/'control.spice',m['input_sha256'][binary[0]])
        if len(found)!=count or [int(w['environment'].get('OMPI_COMM_WORLD_RANK','-1')) for w in found]!=list(range(count)):raise ValueError('complete live MPI rank inventory required')
        namespace=os.readlink(f'/proc/{owner["pid"]}/ns/mnt')
        for rank,w in enumerate(found):
            if w['CPU_affinity']!=[expected[rank]] or w['environment'].get('OMPI_COMM_WORLD_SIZE')!=str(count) or w['environment'].get('OMP_NUM_THREADS')!='1' or w['mount_namespace']!=namespace:raise ValueError('MPI rank affinity/thread/namespace mismatch')
        if os.readlink(f'/proc/{process["pid"]}/ns/mnt')!=namespace:raise ValueError('launcher namespace mismatch')
        launcher_sha=sha(Path(f'/proc/{process["pid"]}/exe'))
        if launcher_sha!=m['input_sha256'].get('/usr/bin/mpirun'):raise ValueError('MPI launcher executable mismatch')
        before,edges=closure(process['pid'],r['library']);after,_=closure(process['pid'],r['library'])
        if before!=after:raise ValueError('live PDK bytes changed during capture')
        for item in [owner,process,*found]:
            if identity(item['pid'])!=item['birth']:raise ValueError('live process identity changed during observation')
        records.append(dict(native=str(native),controller=owner,launcher=process,launcher_executable_sha256=launcher_sha,
            ranks=found,PDK_static_include_superset_sha256=before,include_edges=edges,dependency_files=len(before),
            matches_reference_PDK=before==r['PDK_static_include_superset_sha256'],all_rank_executables_match=True))
        for p in [op,pp,mp]:pins[str(p)]=sha(p)
    verify(pins)
    save(output,dict(input_sha256=pins,records=records,declared_image=str(image),declared_image_sha256=image_sha,
        declared_image_matches_reference=image_sha==r['declared_container_sha256'],all_live_dependencies_match_reference=all(v['matches_reference_PDK'] for v in records),
        capture_scope='live MPI rank and namespace observation; static include superset; not historical launch attestation',
        container_image_binding_proven=False,physical_models_qualified=False,release_ready=False))
    print(json.dumps(dict(cases=len(records),ranks=[len(v['ranks']) for v in records],all_live_dependencies_match_reference=all(v['matches_reference_PDK'] for v in records))))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--native',action='append',type=Path,required=True)
    for n in ['reference','image','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();os.sched_setaffinity(0,{29});run([p.resolve() for p in a.native],a.reference.resolve(),a.image.resolve(),a.output.resolve())
