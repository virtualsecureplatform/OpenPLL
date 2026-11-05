"""Benchmark the coupled detector's initial bias setup without claiming transient completion."""
import json
import os
from pathlib import Path
import re
import time
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease
from compiled_charge import execute


def run():
    out=ROOT/'build/signoff400/prototype_v3_BBPD_coupled_DC_probe_001';out.mkdir(exist_ok=False)
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+120
    save(out/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,cpu_slots=1,memory_GiB=4,automatic_identical_retry=False))
    source=ROOT/'build/signoff400/prototype_v3_BBPD_coupled_TT_pilot_001';manifest=source/'input_manifest.json';m=json.loads(manifest.read_text());verify(m['input_sha256'])
    original=source/'phase_-1000ps/coupled.cir';text=original.read_text();lines=text.splitlines()
    if sum(line.lower().startswith('.tran ') for line in lines)!=1 or sum(line.lower().startswith('.print tran ') for line in lines)!=1:raise ValueError('single transient deck required')
    text='\n'.join('.op' if line.lower().startswith('.tran ') else line for line in lines if not line.lower().startswith('.print tran '))+'\n'
    deck=out/'bias.cir';deck.write_text(text);init=out/'.spiceinit';init.write_text('set ngbehavior=hsa\nset numdgt=15\n')
    image=ROOT/'build/apptainer/openpll-release-modern.sif';ng=ROOT/'build/tools/ngspice47_klu_002/install/bin/ngspice'
    pins=dict(m['input_sha256']);pins.update({str(p):sha(p) for p in (manifest,original,deck,init,Path(__file__).resolve())})
    os.environ.update(OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    log=out/'native.log';started=time.monotonic()
    try:
        save(out/'status.json',dict(state='native_bias_probe_running',release_ready=False))
        with lease(1,4,deadline):execute(['apptainer','exec','--bind','/home:/home,/tmp:/tmp','--pwd',out,image,ng,'-b',deck],log,deadline,4)
        text=log.read_text()
        if 'Using KLU as Direct Linear Solver' not in text or re.findall(r'No\. of Data Rows\s*:\s*(\d+)',text)!=['1']:raise ValueError('one successful native DC point required')
        verify(pins)
        save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(log):sha(log)},native_DC_point_completed=True,
            elapsed_wall_s=time.monotonic()-started,transient_behavior_qualified=False,diagnostic=True,validated_for_prototype=False,release_ready=False))
        save(out/'status.json',dict(state='native_bias_probe_complete',release_ready=False))
    except BaseException as exc:
        save(out/'status.json',dict(state='stopped_without_promotion',reason=repr(exc),release_ready=False));raise


if __name__=='__main__':run()
