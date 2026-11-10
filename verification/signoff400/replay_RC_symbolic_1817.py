"""Replay completed exact CSC input with ordering-boundary diagnostics only."""
import json,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import lease,identity
from compiled_charge_v2 import execute

def run():
    base=ROOT/'build/signoff400';capture=base/'selected_zero_C_backend_CSC_capture_1813';receipt=capture/'assessment.json';r=json.loads(receipt.read_text());verify(r['input_sha256']);verify(r['artifacts'])
    p=json.loads((capture/'native.process.json').read_text())
    if identity(p['pid'])==p['birth'] or not r['native_diagnostic_completed']:raise ValueError('completed exact matrix capture required')
    source=ROOT/'tools/xyce_umfpack/symbolic_replay';out=base/'selected_RC_symbolic_replay_1817';out.mkdir(exist_ok=False);binary=out/'replay';shim=out/'trace.so'
    pins={str(p):sha(p)for p in [receipt,source/'replay.c',source/'trace_cholmod.c',Path(__file__).resolve(),Path('/usr/lib/x86_64-linux-gnu/libumfpack.so.6'),Path('/usr/lib/x86_64-linux-gnu/libcholmod.so.5')]}
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+600
    try:
        with lease(1,16,deadline):
            execute(['/usr/bin/cc','-D_POSIX_C_SOURCE=200809L','-O2','-I/usr/include/suitesparse',source/'replay.c','-lumfpack','-o',binary],out/'build.log',deadline,2)
            execute(['/usr/bin/cc','-O2','-shared','-fPIC','-I/usr/include/suitesparse',source/'trace_cholmod.c','-ldl','-o',shim],out/'shim_build.log',deadline,2)
            control=base/'selected_zero_C_metis_control_1816/adapted/matrix'
            execute(['/usr/bin/env','LD_PRELOAD='+str(shim),binary,control],out/'control.log',deadline,4)
            result=json.loads((out/'control.log').read_text().splitlines()[-1])
            if result['status']!=0 or result['rows']!=3 or result['ordering_used']!=3:raise ValueError('native control symbolic replay failed')
            save(out/'inputs.json',dict(input_sha256=pins,CPU_budget=1,memory_GiB=16,cap_s=600,simulation_solved=False))
            save(out/'status.json',dict(state='replaying_completed_full_CSC_symbolic_analysis'))
            execute(['/usr/bin/env','LD_PRELOAD='+str(shim),binary,capture/'matrix'],out/'full.log',deadline,16)
        verify(pins);save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p)for p in [binary,shim,out/'control.log',out/'full.log']},symbolic_replay_completed=True,simulation_solved=False,release_ready=False));save(out/'status.json',dict(state='symbolic_replay_complete'))
    except BaseException as e:save(out/'status.json',dict(state='stopped_without_qualification',reason=repr(e)));raise
if __name__=='__main__':run()
