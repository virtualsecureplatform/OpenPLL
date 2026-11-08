#!/usr/bin/env python3
"""Build an isolated PBSWGD-default correction on a checked value-gather backend."""
import argparse,difflib,json,os,shlex,shutil,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'verification/signoff400'))
from runtime_common import save,sha
from resources import lease,identity
from compiled_charge_v2 import execute
from build import archive_members


def verify(pins):
    for path,expected in pins.items():
        if sha(path)!=expected:raise ValueError('Input changed: '+path)

def correct_default(text):
    old='  if (!given("PBSWGD"))\n    DGatesidewallJctPotential = DsidewallJctPotential;'
    new='  if (!given("PBSWGD"))\n    DGatesidewallJctPotential = SGatesidewallJctPotential;'
    if text.count(old)!=1:raise ValueError('one pinned omitted-PBSWGD default site required')
    return text.replace(old,new)

def run(base,output,cpu):
    receipt=base/'assessment.json';r=json.loads(receipt.read_text());verify(r['input_sha256'])
    archive=base/'libxyce.a';old_binary=base/'Xyce'
    if sha(old_binary)!=r['binary_sha256'] or r['experimental_reuse_policy']!='value-gather':raise ValueError('checked value-gather base required')
    source=Path('/opt/Xyce/src/DeviceModelPKG/OpenModels');build=Path('/opt/xyce-build/src');flags=build/'CMakeFiles/XyceLib.dir/flags.make';link=build/'CMakeFiles/Xyce.dir/link.txt';names=['N_DEV_MOSFET_B4p61.C','N_DEV_MOSFET_B4p70.C','N_DEV_MOSFET_B4p82.C']
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1800;os.sched_setaffinity(0,{cpu});os.environ.update(OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1');save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())));
    pins={str(p):sha(p)for p in [receipt,archive,old_binary,flags,link,Path(__file__).resolve(),Path(__file__).with_name('build.py'),*[source/n for n in names]]};patch=[]
    for name in names:
        original=(source/name).read_text();changed=correct_default(original);target=output/name;target.write_text(changed);pins[str(target)]=sha(target);patch.extend(difflib.unified_diff(original.splitlines(True),changed.splitlines(True),fromfile='a/src/DeviceModelPKG/OpenModels/'+name,tofile='b/src/DeviceModelPKG/OpenModels/'+name))
    patchfile=output/'bsim_PBSWGD_default.patch';patchfile.write_text(''.join(patch));pins[str(patchfile)]=sha(patchfile)
    settings={}
    for line in flags.read_text().splitlines():
        if ' = 'in line:
            key,value=line.split(' = ',1);settings[key]=shlex.split(value)
    objects=[output/(name+'.o')for name in names];commands=[['/usr/bin/mpicxx',*settings['CXX_DEFINES'],*settings['CXX_INCLUDES'],*settings['CXX_FLAGS'],'-c',output/name,'-o',obj]for name,obj in zip(names,objects)]
    target=output/'libxyce.a';binary=output/'Xyce';commands.append(['/usr/bin/ar','rcs',target,*objects]);command=shlex.split(link.read_text())
    if command.count('libxyce.a')!=1:raise ValueError('one checked archive link required')
    command[command.index('libxyce.a')]=str(target);command[command.index('-o')+1]=str(binary);command.append('-lumfpack');commands.append(command)
    baseline_link=list(command);baseline_link[baseline_link.index('-o')+1]=str(output/'base_relinked_Xyce');commands.insert(0,baseline_link)
    save(output/'manifest.json',dict(input_sha256=pins,commands=[[str(v)for v in c]for c in commands],base=str(base),CPU=cpu,memory_GiB=16,wall_limit_s=1800,automatic_identical_retry=False,stock_inputs_modified=False,release_ready=False))
    try:
        verify(pins)
        with lease(1,16,deadline):
            with archive.open('rb')as src,target.open('xb')as dst:shutil.copyfileobj(src,dst,1024*1024)
            os.chdir(build)
            for i,command in enumerate(commands):
                save(output/'status.json',dict(state='building_isolated_BSIM_default_correction',stage=i,release_ready=False));execute(command,output/f'stage_{i}.log',deadline,16)
                if i==0 and sha(output/'base_relinked_Xyce')!=r['binary_sha256']:raise ValueError('cached base archive does not reproduce the checked executable')
            before,after=archive_members(archive),archive_members(target);changed=sorted(k for k in before if before[k]!=after.get(k))
            if before.keys()!=after.keys() or changed!=sorted(p.name for p in objects):raise ValueError('unexpected archive changes')
            execute([binary,'-capabilities'],output/'capabilities.log',deadline,16)
        verify(pins);save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p)for p in [binary,patchfile,output/'capabilities.log']},base_binary_sha256=r['binary_sha256'],binary_sha256=sha(binary),changed_archive_members=changed,all_other_archive_members_identical=True,baseline_archive_relink_exactly_reproduces_checked_binary=True,stock_inputs_modified=False,diode_and_solver_objects_unchanged=True,native_validation_required=True,release_ready=False));save(output/'status.json',dict(state='isolated_BSIM_default_correction_built',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),automatic_identical_retry=False,release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--cpu',type=int,default=min(os.sched_getaffinity(0)));a=p.parse_args();run(a.base.resolve(),a.output.resolve(),a.cpu)
