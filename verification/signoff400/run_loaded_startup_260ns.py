from pathlib import Path
import os,sys,time,json,hashlib
root=Path.cwd();sys.path.insert(0,str(root/'verification/signoff400'))
from resources import lease,identity
from compiled_charge_v2 import execute
from analyze_xyce_runtime import analyze
import argparse
parser=argparse.ArgumentParser()
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
original=root/'build/signoff400/prototype_v3_Xyce_full_C_programming_pilot_030'
tool=root/'build/tools/xyce_umfpack_value_gather_001'
helper=root/'tools/xyce_umfpack/rank_exec.py'
def save(n,d):(out/n).write_text(json.dumps(d,indent=2)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert json.loads((root/'build/signoff400/value_gather_native_controls_128/assessment.json').read_text())['all_native_controls_complete_and_agree']
deck=out/'profile.spice';raw=out/'profile.raw'
text=(original/'programming.spice').read_text().replace(str(original/'programming.raw'),str(raw))
assert 'exittime' not in text.lower()
assert '.tran 10p 175n 0 1n' in text
text=text.replace('.tran 10p 175n 0 1n','.tran 10p 260n 0 10p')
deck.write_text(text.replace('.end\n','.options DIST STRATEGY=2\n.end\n'))
from common_v3 import source_pins
save('candidate_snapshot.json',dict(source_sha256=source_pins(),active_release=json.loads((root/'verification/active_release.json').read_text())))
inputs=[root/'verification/signoff400/requirements_v3.json',out/'candidate_snapshot.json',deck,original/'model.spice',tool/'Xyce',tool/'CheckedUMFPACK.h',helper,Path(__file__).resolve()];pins={str(p):sha(p) for p in inputs}
start=time.clock_gettime(time.CLOCK_BOOTTIME);deadline=start+172500
save('manifest.json',dict(input_sha256=pins,CPUs=list(range(16)),MPI_ranks=16,root_solver_threads=1,root_affinity=[0],memory_GiB=64,required_end_s=260e-9,measurement_start_s=200e-9,maximum_step_s=10e-12,reset_release_s=180e-9,qualification_pending=True,release_ready=False))
save('owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
os.sched_setaffinity(0,set(range(16)));os.environ.update(OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1')
save('status.json',dict(state='running_loaded_startup_260ns',started_uptime=start,native_deadline_uptime=deadline))
try:
 with lease(16,64,deadline):execute(['/usr/bin/mpirun','--bind-to','none','-np','16','/usr/bin/python3',helper,'--cpus',','.join(map(str,range(16))),'--',tool/'Xyce','-a','-linsolv','umfpack_reuse',deck],out/'native.log',deadline,48)
 elapsed=time.clock_gettime(time.CLOCK_BOOTTIME)-start
 save('timing.json',analyze(out/'native.log'))
 for p,h in pins.items():assert sha(Path(p))==h
 save('status.json',dict(state='native_startup_completed_waveform_assessment_pending',native_elapsed_s=elapsed,release_ready=False))
except Exception as e:
 save('status.json',dict(state='stopped_without_qualification',reason=repr(e),release_ready=False));raise
