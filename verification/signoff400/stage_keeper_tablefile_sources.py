"""Generate literal boundary files on local scratch and retain a verified archive."""
import argparse,json,tempfile,time,tarfile,hashlib,os
from pathlib import Path
from common_v3 import save,sha,verify
from resources import identity,lease
from write_keeper_tablefile_sources import run as generate


def archive_sources(receipt,destination):
    a=json.loads(receipt.read_text());verify(a['artifacts'])
    root=receipt.parent.resolve();members={}
    for path,digest in {**a['artifacts'],str(receipt):sha(receipt)}.items():
        p=Path(path).resolve()
        if not p.is_relative_to(root) or not p.is_file() or Path(path).is_symlink():raise ValueError('regular source artifacts inside source root required')
        members[str(p.relative_to(root))]=digest
    if set(members)!={str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()}:raise ValueError('complete source-tree artifact inventory required')
    with tarfile.open(destination,'x') as archive:
        for name in sorted(members):
            p=root/name;info=archive.gettarinfo(str(p),arcname=name)
            info.uid=info.gid=0;info.uname=info.gname='';info.mtime=0;info.mode=0o644
            with p.open('rb') as stream:archive.addfile(info,stream)
    with tarfile.open(destination,'r') as archive:
        names=archive.getnames()
        if len(names)!=len(members) or set(names)!=set(members):raise ValueError('source archive inventory mismatch')
        for entry in archive:
            if not entry.isfile():raise ValueError('regular archived source files required')
            h=hashlib.sha256()
            with archive.extractfile(entry) as stream:
                for block in iter(lambda:stream.read(8*1024*1024),b''):h.update(block)
            if h.hexdigest()!=members[entry.name]:raise ValueError('source archive contents mismatch')
    verify(a['artifacts'])
    return dict(original_source_root=str(root),source_archive_members=members,all_source_archive_members_hash_verified=True,source_archive_path_relocation_performed=False)


def run(waveforms,output,shared_knots=False):
    generator_script=Path(__file__).with_name('write_keeper_shared_tablefile_sources.py' if shared_knots else 'write_keeper_tablefile_sources.py')
    if shared_knots:
        from write_keeper_shared_tablefile_sources import run as generate_sources
    else:generate_sources=generate
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{29});save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())));deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+7200
    try:
        with lease(1,8,deadline):
            local=Path(tempfile.mkdtemp(prefix='openpll-tablefile-'))/'sources'
            save(output/'status.json',dict(state='generating_local_boundary_sources',local_sources=str(local),release_ready=False));start=time.monotonic();generate_sources(waveforms,local);generation_s=time.monotonic()-start
            save(output/'status.json',dict(state='archiving_and_verifying_local_sources',release_ready=False));archive=output/'sources.tar';start=time.monotonic();inventory=archive_sources(local/'assessment.json',archive);archive_s=time.monotonic()-start
            pins={str(p):sha(p) for p in [waveforms/'assessment.json',local/'assessment.json',Path(__file__).resolve(),Path(__file__).with_name('write_keeper_tablefile_sources.py'),generator_script]}
            save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(archive):sha(archive)},**inventory,local_sources=str(local),shared_knot_carrier_requested=shared_knots,source_generation_s=generation_s,archive_and_verification_s=archive_s,native_execution_performed=False,full_source_preparation_speedup_demonstrated=False,release_ready=False));save(output/'status.json',dict(state='local_sources_and_verified_archive_complete',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['waveforms','output']:p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--shared-knots',action='store_true');a=p.parse_args();run(a.waveforms.resolve(),a.output.resolve(),a.shared_knots)
