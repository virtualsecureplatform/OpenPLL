#!/usr/bin/env python3
"""Build an isolated call-boundary initialization tracer on the checked corrected backend."""
import argparse,difflib,json,os,shlex,shutil,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'verification/signoff400'))
from common_v3 import save,sha,verify
from resources import lease,identity
from compiled_charge_v2 import execute
from build import archive_members

def trace_headers(source,output):
    files=['N_LAS_OpenPLLUMFPACKSolver.h','CheckedUMFPACK.h']
    for name in files:
        text=(source/name).read_text()
        if name.startswith('N_LAS'):
            targets=[('transform','if(!Teuchos::is_null(transform_)){if(!transformed_)transformed_=&((*transform_)(*original_));transform_->fwd();problem=transformed_;}'),
                     ('gather_values','if(update)status=gatherValues(*matrix);'),
                     ('prepare_values','if(update)prepareGatheredValues();')]
            for label,old in targets:
                if text.count(old)!=1:raise ValueError(label)
                text=text.replace(old,'std::cerr<<"OPENPLL_LINEAR_TRACE begin '+label+'"<<std::endl;'+old+'std::cerr<<"OPENPLL_LINEAR_TRACE end '+label+'"<<std::endl;')
            old='  if(!rootMap_){'
            if text.count(old)!=1:raise ValueError('root map')
            text=text.replace(old,old+'std::cerr<<"OPENPLL_LINEAR_TRACE begin root_matrix"<<std::endl;')
            old='rootMatrix_->OptimizeStorage();'
            if text.count(old)!=1:raise ValueError('root matrix')
            text=text.replace(old,old+'std::cerr<<"OPENPLL_LINEAR_TRACE end root_matrix"<<std::endl;')
        else:
            text='#include <iostream>\n'+text
            for label,prefix in [('symbolic','int status = umfpack_di_symbolic('),('numeric','int status = umfpack_di_numeric(')]:
                if text.count(prefix)!=1:raise ValueError(label)
                a=text.index(prefix);b=text.index(';',a)+1;statement=text[a:b]
                text=text[:a]+'std::cerr<<"OPENPLL_LINEAR_TRACE begin '+label+'"<<std::endl;'+statement+'std::cerr<<"OPENPLL_LINEAR_TRACE end '+label+'"<<std::endl;'+text[b:]
        (output/name).write_text(text)
    return [output/name for name in files]


def run(base,output):
    receipt=base/'assessment.json';r=json.loads(receipt.read_text());verify(r['input_sha256'])
    archive=base/'libxyce.a';old_binary=base/'Xyce'
    if sha(old_binary)!=r['binary_sha256']:raise ValueError('checked value-gather base required')
    source=ROOT/'build/tools/xyce_umfpack_value_gather_001';build=Path('/opt/xyce-build/src');flags=build/'CMakeFiles/XyceLib.dir/flags.make';link=build/'CMakeFiles/Xyce.dir/link.txt';names=['N_LAS_TranSolverFactory.C']
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1800;os.sched_setaffinity(0,{28});os.environ.update(OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1');save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())));
    pins={str(p):sha(p)for p in [receipt,archive,old_binary,flags,link,Path(__file__).resolve(),Path(__file__).with_name('build.py'),*[source/n for n in names]]};patch=[];headers=trace_headers(source,output);pins.update({str(p):sha(p)for p in [*headers,*[source/n for n in ['N_LAS_OpenPLLUMFPACKSolver.h','CheckedUMFPACK.h']]]})
    for name in names:
        original=(source/name).read_text();changed=original;target=output/name;target.write_text(changed);pins[str(target)]=sha(target);patch.extend(difflib.unified_diff(original.splitlines(True),changed.splitlines(True),fromfile='a/src/CircuitPKG/'+name,tofile='b/src/CircuitPKG/'+name))
    patchfile=output/'initialization_trace.patch';patchfile.write_text(''.join(patch));pins[str(patchfile)]=sha(patchfile)
    settings={}
    for line in flags.read_text().splitlines():
        if ' = 'in line:
            key,value=line.split(' = ',1);settings[key]=shlex.split(value)
    objects=[output/(name+'.o')for name in names];commands=[['/usr/bin/mpicxx','-I'+str(output),*settings['CXX_DEFINES'],*settings['CXX_INCLUDES'],*settings['CXX_FLAGS'],'-c',output/name,'-o',obj]for name,obj in zip(names,objects)]
    target=output/'libxyce.a';binary=output/'Xyce';commands.append(['/usr/bin/ar','rcs',target,*objects]);command=shlex.split(link.read_text())
    if command.count('libxyce.a')!=1:raise ValueError('one checked archive link required')
    command[command.index('libxyce.a')]=str(target);command[command.index('-o')+1]=str(binary);command.append('-lumfpack');commands.append(command)
    baseline_link=list(command);baseline_link[baseline_link.index('-o')+1]=str(output/'base_relinked_Xyce');commands.insert(0,baseline_link)
    save(output/'manifest.json',dict(input_sha256=pins,commands=[[str(v)for v in c]for c in commands],base=str(base),CPU=28,memory_GiB=16,wall_limit_s=1800,automatic_identical_retry=False,stock_inputs_modified=False,release_ready=False))
    try:
        verify(pins)
        with lease(1,16,deadline):
            with archive.open('rb')as src,target.open('xb')as dst:shutil.copyfileobj(src,dst,1024*1024)
            os.chdir(build)
            for i,command in enumerate(commands):
                save(output/'status.json',dict(state='building_isolated_initialization_trace',stage=i,release_ready=False));execute(command,output/f'stage_{i}.log',deadline,16)
                if i==0 and sha(output/'base_relinked_Xyce')!=r['binary_sha256']:raise ValueError('cached base archive does not reproduce the checked executable')
            before,after=archive_members(archive),archive_members(target);changed=sorted(k for k in before if before[k]!=after.get(k))
            if before.keys()!=after.keys() or changed!=sorted(p.name for p in objects):raise ValueError('unexpected archive changes')
            execute([binary,'-capabilities'],output/'capabilities.log',deadline,16)
        verify(pins);save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p)for p in [binary,patchfile,output/'capabilities.log']},base_binary_sha256=r['binary_sha256'],binary_sha256=sha(binary),changed_archive_members=changed,all_other_archive_members_identical=True,baseline_archive_relink_exactly_reproduces_checked_binary=True,stock_inputs_modified=False,device_objects_unchanged=True,linear_adapter_trace_only=True,trace_only=True,native_validation_required=True,release_ready=False));save(output/'status.json',dict(state='isolated_initialization_trace_built',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),automatic_identical_retry=False,release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.base.resolve(),a.output.resolve())
