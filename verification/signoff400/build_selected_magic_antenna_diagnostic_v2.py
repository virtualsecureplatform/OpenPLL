"""Build an isolated, logging-only Magic diagnostic from verified source.

Never replaces the release executable or modifies PDK rules/layout inputs.
"""
import argparse,json,os,shutil,subprocess,time,tempfile
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease


def run(review,output):
    output.mkdir(parents=True,exist_ok=False)
    os.sched_setaffinity(0,{29})
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+3600
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    try:
        receipt=ROOT/'build/signoff400/selected_magic_source_reproducibility_600.json'
        r=json.loads(receipt.read_text());verify(r['input_sha256'])
        if not r['matches_retained_pinned_source']:raise ValueError('verified source required')
        source=review/'unpacked/magic-8.3.623'
        from verify_selected_magic_source_identity import nar_hash
        if nar_hash(source)!=r['recursive_NAR_sha256']:raise ValueError('source tree identity changed')
        pins={str(p):sha(p) for p in [Path(__file__).resolve(),Path(__file__).with_name('verify_selected_magic_source_identity.py'),receipt]}
        save(output/'inputs.json',dict(input_sha256=pins,source_NAR=r['recursive_NAR_sha256'],release_tool_replaced=False,PDK_mutated=False,release_ready=False))
        with lease(1,4,deadline):
            work=Path(tempfile.mkdtemp(prefix='openpll-magic-diagnostic-'));shutil.copytree(source,work,symlinks=True,dirs_exist_ok=True);save(output/'workspace.json',dict(local_source=str(work),temporary_diagnostic_only=True))
            target=work/'extflat/EFantenna.c';text=target.read_text()
            old='    area = (dlong)(nx * ny) * (dlong)(fcutsize * fcutsize);'
            new=old+'\n    TxPrintf("OPENPLL_CONTACT type=%d plane=%d cuts=%d,%d cut=%g scale=%d area=%g userlimit=%d\\n", type, plane, nx, ny, fcutsize, CIFCurStyle->cs_scaleFactor, (double)area, DBNumUserLayers);'
            if text.count(old)!=1:raise ValueError('unique exact contact calculation required')
            text=text.replace(old,new)
            old='\t\tantennaError = FALSE;'
            new='''        TxPrintf("OPENPLL_STAGE plane=%d gate=%g diffusion=%g\\n", pNum2, (double)gatearea, (double)diffarea);
        for (i = 0; i < DBNumUserLayers; i++)
            if (DBIsContact(i) && ExtCurStyle->exts_antennaRatio[i].ratioGate > 0)
                TxPrintf("OPENPLL_CONTACT_TOTAL type=%d base=%d plane=%d area=%g ratio=%g\\n", i, DBPlane(i), pNum2, (double)antennaarea[i], (double)ExtCurStyle->exts_antennaRatio[i].ratioGate);
'''+old
            if text.count(old)!=1:raise ValueError('unique stage diagnostic insertion required')
            target.write_text(text.replace(old,new));save(output/'instrumentation.json',dict(original=sha(source/'extflat/EFantenna.c'),instrumented=sha(target),behavior_change='logging only',qualification=False))
            tcl='/nix/store/biz055ybc5x1vxar1dqlrjsw7w9axgc2-tcl-8.6.16'
            tk='/nix/store/qg5pfny16idn650ym2m2sgjbrhgjyw17-tk-8.6.16'
            tkdev='/nix/store/sycnvm378252y56g62z554vjm6agcidl-tk-8.6.16-dev'
            command=['./configure','--prefix='+str(output/'install'),'--with-tcl='+tcl+'/lib','--with-tk='+tk+'/lib','--with-tclincls='+tcl+'/include','--with-tkincls='+tkdev+'/include','--with-tcllibs='+tcl+'/lib','--with-tklibs='+tk+'/lib','--with-opengl=no','--with-cairo=no','--without-x','--disable-readline']
            env=dict(os.environ,CFLAGS='-O0 -g -I/nix/store/c8zanvqhjwpsi130933vdcfpp8454yc4-libx11-1.8.12-dev/include -I/nix/store/mq1y6y0ckk5i7xga1ly68325pn14n2wz-xorgproto-2024.1/include',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
            for name,cmd in [('configure',command),('make',['make','-j1']),('install',['make','install'])]:
                save(output/'status.json',dict(state='diagnostic_'+name,release_ready=False))
                with (output/(name+'.log')).open('x') as log:
                    subprocess.run(cmd,cwd=work,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=max(1,deadline-time.clock_gettime(time.CLOCK_BOOTTIME)))
            verify(pins)
            save(output/'status.json',dict(state='isolated_diagnostic_build_complete',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['review','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.review.resolve(),a.output.resolve())
