"""Capture the exact assembled first-DC CSC matrix as a completed diagnostic product."""
import json,time,os
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease
from compiled_charge_v2 import execute

def run():
    base=ROOT/'build/signoff400';source=base/'selected_full_RC_linear_trace_1788'
    record=json.loads((source/'inputs.json').read_text());verify(record['input_sha256'])
    build=ROOT/'build/tools/xyce_CSC_capture_1794/assessment.json';control=base/'selected_CSC_capture_control_1799/assessment.json'
    br,cr=[json.loads(p.read_text())for p in [build,control]]
    for r in [br,cr]:verify(r['input_sha256']);verify(r['artifacts'])
    if not cr['exact_analytical_MNA_capture'] or not cr['pass_through_DC_unchanged']:raise ValueError('validated exact capture required')
    startup=base/'selected_floating_C_startup_1802/assessment.json';sr=json.loads(startup.read_text());verify(sr['input_sha256']);verify(sr['artifacts'])
    if not sr['analytical_floating_charge_relation_verified'] or not sr['first_transient_matrix_has_no_zero_rows']:raise ValueError('validated floating-charge startup required')
    binary=ROOT/'build/tools/xyce_linear_trace_1786/Xyce';shim=build.parent/'capture_symbolic.so';deck=source/'smoke.spice'
    if record['input_sha256'].get(str(binary))!=sha(binary) or record['input_sha256'].get(str(deck))!=sha(deck):raise ValueError('frozen full deck and backend required')
    out=base/'selected_full_RC_UIC_CSC_capture_1803';out.mkdir(exist_ok=False)
    original_deck=deck;text=deck.read_text();old=str(source/'dc.csv')
    if text.count(old)!=1:raise ValueError('one diagnostic output filename required')
    if text.count('.dc VRESET 0 0 1')!=1:raise ValueError('one reset DC analysis required')
    text=text.replace('.dc VRESET 0 0 1','.tran 1p 200p 0 10p UIC').replace('.print dc ','.print tran ')
    lines=[];ramps=0
    for line in text.splitlines():
        f=line.split()
        if len(f)==4 and f[0].startswith('V') and f[2]=='0' and f[3]=='1.8':
            line=' '.join(f[:3])+' PWL(0 0 100p 1.8 200p 1.8)';ramps+=1
        lines.append(line)
    if ramps==0:raise ValueError('explicit high input/supply ramps required')
    text='\n'.join(lines)+'\n'
    deck=out/'capture.spice';deck.write_text(text.replace(old,str(out/'unused_dc.csv')).replace('\n.end\n','\n.options topology outputnamesfile=1\n.end\n'))
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1800;os.sched_setaffinity(0,{21})
    pins={**record['input_sha256'],**{str(p):sha(p)for p in [source/'inputs.json',build,control,startup,shim,deck,Path(__file__).resolve()]}}
    save(out/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    save(out/'inputs.json',dict(input_sha256=pins,CPU=21,memory_GiB=64,cap_s=1800,diagnostic_matrix_only=True,simulation_solved=False,UIC_zero_charge_startup=True,supply_ramp_ps=100,high_input_ramps=ramps))
    try:
        save(out/'status.json',dict(state='waiting_for_capture_resource_lease'))
        with lease(1,64,deadline):
            save(out/'status.json',dict(state='native_matrix_capture_running'))
            os.chdir(out)
            execute(['/usr/bin/env','LD_PRELOAD='+str(shim),'OPENPLL_CSC_CAPTURE='+str(out/'matrix'),binary,'-a','-linsolv','umfpack_reuse',deck.name],out/'native.log',deadline,64)
        verify(pins);done=json.loads((out/'matrix/completion.json').read_text());log=(out/'native.log').read_text()
        if not done['exact_binary_CSC_capture_complete'] or done['simulation_solved'] or 'OPENPLL_CSC_CAPTURE_COMPLETE' not in log:raise ValueError('normal diagnostic completion required')
        save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p)for p in [*(out/'matrix').iterdir(),out/'native.log',out/'namesMap_capture.spice.txt']},native_diagnostic_completed=True,exact_binary_CSC_capture_complete=True,simulation_solved=False,RC_backend_qualified=False,release_ready=False))
        save(out/'status.json',dict(state='completed_exact_CSC_diagnostic'))
    except BaseException as e:
        save(out/'status.json',dict(state='stopped_without_qualification',reason=repr(e)));raise
if __name__=='__main__':run()
