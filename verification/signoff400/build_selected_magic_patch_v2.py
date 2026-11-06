"""Build the experimental antenna patch from a pinned archive and toolchain.

Installs only into a new output directory. Never replaces the release tool.
"""
import argparse,json,os,resource,subprocess,tarfile,tempfile,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease
from verify_selected_magic_source_identity import nar_hash


def run(archive,patch,toolchain,output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{29})
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())));deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+3600
    try:
        config=json.loads(toolchain.read_text());image=ROOT/'build/apptainer/openpll-release-modern.sif'
        if sha(archive)!=config['archive_sha256'] or sha(image)!=config['image_sha256']:raise ValueError('pinned archive and container required')
        files=[Path(__file__).resolve(),Path(__file__).with_name('verify_selected_magic_source_identity.py'),archive,patch,toolchain,image,Path('/usr/bin/gcc'),Path('/usr/bin/make'),Path(config['patch_executable'])]
        pins={str(p):sha(p) for p in files}
        save(output/'inputs.json',dict(input_sha256=pins,source_revision=config['source_revision'],source_NAR=config['source_NAR'],toolchain_config=str(toolchain),release_tool_replaced=False,release_ready=False))
        with lease(1,4,deadline):
            resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
            workroot=Path(tempfile.mkdtemp(prefix='openpll-magic-patch-'))
            with tarfile.open(archive) as source:source.extractall(workroot,filter='data')
            children=list(workroot.iterdir())
            if len(children)!=1 or not children[0].is_dir() or children[0].is_symlink():raise ValueError('unique real source root required')
            work=children[0]
            if nar_hash(work)!=config['source_NAR']:raise ValueError('source NAR identity differs')
            save(output/'workspace.json',dict(local_source=str(work),source_NAR_verified=True))
            with (output/'patch.log').open('x') as log:subprocess.run([config['patch_executable'],'--batch','--fuzz=0','-p1','-i',str(patch)],cwd=work,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=60)
            tcl=config['tcl_root'];tk=config['tk_root'];prefix=output/'install'
            command=['./configure','--prefix='+str(prefix),'--with-tcl='+tcl+'/lib','--with-tk='+tk+'/lib','--with-tclincls='+tcl+'/include','--with-tkincls='+config['tk_include'],'--with-tcllibs='+tcl+'/lib','--with-tklibs='+tk+'/lib','--with-opengl=no','--with-cairo=no','--without-x','--disable-readline']
            env=dict(os.environ,CFLAGS='-O2 -g '+' '.join('-I'+p for p in config['x11_includes']),OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
            for name,cmd in [('configure',command),('make',['make','-j1']),('install',['make','install'])]:
                save(output/'status.json',dict(state='patch_build_'+name,release_ready=False))
                with (output/(name+'.log')).open('x') as log:subprocess.run(cmd,cwd=work,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=max(1,deadline-time.clock_gettime(time.CLOCK_BOOTTIME)))
            verify(pins)
            save(output/'instrumentation.json',dict(patch_sha256=sha(patch),patched_source_sha256=sha(work/'extflat/EFantenna.c'),diagnostic_logging_added=False,release_qualified=False))
            save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in prefix.rglob('*') if p.is_file()},source_NAR_verified=True,patch_applied_without_fuzz=True,release_tool_replaced=False,antenna_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='isolated_diagnostic_build_complete',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['archive','patch','toolchain','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['archive','patch','toolchain','output']))
