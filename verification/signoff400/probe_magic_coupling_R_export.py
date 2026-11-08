"""Small native two-wire control for coupling handling during extresist export."""
import argparse,json,os,time
from pathlib import Path
from common_v3 import save,sha,verify
from resources import lease,identity
from compiled_charge_v2 import execute
from replay_keeper_flat_signed_C import MAGIC,TECH
from audit_keeper_native_R_contraction import compare,parse
from fractions import Fraction as F

def run(output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{27});os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1');deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+180
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())));rc=output/'minimal.magicrc';rc.write_text(f'tech load {{{TECH}}}\ndrc off\ncrashbackups disable\nlocking disable\n')
    script=output/'probe.tcl';before=output/'before.spice';after=output/'after.spice';top='OpenPLL_Coupling_R_Probe'
    script.write_text(f'''cd {{{output}}}
if {{[catch {{
load {top}
box values 0 0 4000 100
paint m1
label A center m1
port make 1
box values 0 120 4000 220
paint m1
label B center m1
port make 2
extract style ngspice()
extract do local
extract do capacitance
extract do coupling
extract do resistance
extract warn all
extresist include A
extresist simplify off
extract all
ext2spice lvs
ext2spice hierarchy off
ext2spice subcircuit top on
ext2spice short resistor
ext2spice cthresh -1e100
ext2spice extresist off
ext2spice -o {{{before}}} {top}.ext
extresist all
ext2spice extresist on
ext2spice -o {{{after}}} {top}.ext
feedback save {{{output/'feedback.txt'}}}
}} error]}} {{puts stderr $error; exit 1}}
quit -noprompt
''')
    folder=Path(__file__).resolve().parent;files=[rc,script,MAGIC,TECH,Path(__file__).resolve(),folder/'audit_keeper_native_R_contraction.py',folder/'native_spice_comments.py',folder/'compiled_charge_v2.py'];pins={str(p):sha(p) for p in files};save(output/'inputs.json',dict(input_sha256=pins,geometry='two separate parallel metal1 rectangles, 4000x100 internal units, gap 20',only_requested_R_net='A',CPU=27,memory_GiB=4,native_cap_s=180,maximum_native_cases=1,automatic_identical_retry=False,release_ready=False))
    try:
        save(output/'status.json',dict(state='native_two_wire_coupling_probe_running',release_ready=False))
        with lease(1,4,deadline):execute([MAGIC,'-nowrapper','-dnull','-noconsole','-rcfile',rc,script],output/'native.log',deadline,4)
        verify(pins);metrics=compare(before.read_text(),after.read_text());data=parse(before.read_text());coupling=sum((v for a,b,v in data['caps'] if {a,b}=={'a','b'}),F(0))
        artifacts=[before,after,output/(top+'.ext'),output/(top+'.res.ext'),output/'native.log',output/'feedback.txt']
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in artifacts},normal_native_completion=True,original_A_B_coupling_F_exact=str(coupling),original_A_B_coupling_fF=float(coupling*10**15),contraction=metrics,distributed_wire_R_qualified=False,model_qualified=False,release_ready=False));save(output/'status.json',dict(state='two_wire_coupling_probe_complete',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.output.resolve())
