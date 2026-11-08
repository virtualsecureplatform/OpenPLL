"""C-only control on the exact flat GDS used by the native resistance pilot."""
import argparse,json,os,time
from pathlib import Path
from common_v3 import save,sha,verify
from resources import identity,lease
from compiled_charge_v2 import execute
from replay_keeper_flat_signed_C import MAGIC,TECH
from extract_keeper_flat_geometry_C import FLAT

def run(flat,output):
    receipt=flat/'assessment.json';a=json.loads(receipt.read_text());verify(a['input_sha256']);verify(a['artifacts']);gds=flat/'flat.gds'
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{26});os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1');deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1200
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline));rc=output/'minimal.magicrc';rc.write_text(f'tech load {{{TECH}}}\ndrc off\ncrashbackups disable\nlocking disable\n');script=output/'extract.tcl';model=output/'capacitance.spice'
    script.write_text(f'''cd {{{output}}}
if {{[catch {{
gds read {{{gds}}}
load {FLAT}
select top cell
extract style ngspice()
extract do local
extract do capacitance
extract do coupling
extract no resistance
extract warn all
extract all
ext2spice lvs
ext2spice hierarchy off
ext2spice subcircuit top on
ext2spice short resistor
ext2spice cthresh -1e100
ext2spice extresist off
ext2spice -o {{{model}}} {FLAT}.ext
feedback save {{{output/'feedback.txt'}}}
}} error]}} {{puts stderr $error; exit 1}}
quit -noprompt
''')
    folder=Path(__file__).resolve().parent;files=[receipt,gds,rc,script,MAGIC,TECH,Path(__file__).resolve(),folder/'compiled_charge_v2.py',folder/'replay_keeper_flat_signed_C.py',folder/'extract_keeper_flat_geometry_C.py'];pins={str(p):sha(p) for p in files};save(output/'inputs.json',dict(input_sha256=pins,full_RC_extraction_mode=False,distributed_R_export=False,CPU=26,memory_GiB=16,native_cap_s=1200,maximum_native_cases=1,automatic_identical_retry=False,release_ready=False))
    try:
        save(output/'status.json',dict(state='reloaded_flat_C_only_extraction_running',release_ready=False))
        with lease(1,16,deadline):execute([MAGIC,'-nowrapper','-dnull','-noconsole','-rcfile',rc,script],output/'native.log',deadline,16)
        verify(pins);artifacts=[model,output/(FLAT+'.ext'),output/'native.log',output/'feedback.txt']
        if any(not p.exists() for p in artifacts):raise ValueError('complete native artifacts required')
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in artifacts},normal_native_completion=True,full_RC_extraction_mode=False,distributed_R_export=False,source_GDS_sha256=sha(gds),capacitance_equivalence_verified=False,model_qualified=False,release_ready=False));save(output/'status.json',dict(state='reloaded_flat_C_only_extraction_complete_audit_pending',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['flat','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.flat.resolve(),a.output.resolve())
