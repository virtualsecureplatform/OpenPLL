"""Controlled streaming assessor for future sequential propagation jobs."""
import json
from pathlib import Path
import subprocess
import time
from run_dco_qualification import sha,save


def assess(plan,pins,out,deadline,controls):
    out=Path(out).resolve();controls=Path(controls).resolve();proof=controls/'assessment.json';c=json.loads(proof.read_text())
    binary=controls/'assess_sequential_waveform'
    if not c['compiled_streaming_sequential_assessor_matches_all_retained_records'] or not c['invalid_waveform_controls_rejected']:
        raise ValueError('controlled compiled assessor required')
    if sha(binary)!=c['artifacts'][str(binary)]:raise ValueError('controlled assessor binary changed')
    if (out/'assessment.json').exists():raise FileExistsError('preserve previous native assessment')
    pins=dict(pins);pins.update({str(proof):sha(proof),str(binary):sha(binary),str(Path(__file__).resolve()):sha(Path(__file__).resolve())})
    wave=out/'batch.prn';pins[str(wave)]=sha(wave)
    for name,digest in pins.items():
        if sha(Path(name))!=digest:raise ValueError('propagation assessment input changed: '+name)
    remaining=deadline-time.clock_gettime(time.CLOCK_BOOTTIME)
    if remaining<=0:raise TimeoutError('propagation assessment deadline')
    cfg=out/'compiled_assessor.json';report=out/'compiled_assessor.report.json'
    # The parser consumes only fixture inversion metadata; keep a separately pinned
    # serialization of the complete caller plan so no implicit plan lookup occurs.
    local_plan=out/'compiled_assessor.plan.json';save(local_plan,plan)
    save(cfg,dict(plan=str(local_plan),waveform=str(wave),deadline_uptime=deadline,report=str(report)))
    pins[str(local_plan)]=sha(local_plan);pins[str(cfg)]=sha(cfg)
    with (out/'compiled_assessor.log').open('x') as log:
        subprocess.run([str(binary),str(cfg)],check=True,stdout=log,stderr=subprocess.STDOUT,timeout=remaining)
    r=json.loads(report.read_text())
    if r['fixtures']!=len(plan['fixtures']) or not r['all_native_waveform_events_terminal']:raise ValueError('complete propagation assessment required')
    for name,digest in pins.items():
        if sha(Path(name))!=digest:raise ValueError('input changed during compiled assessment')
    if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('compiled assessment exceeded deadline')
    artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file() and p.name!='status.json'}
    save(out/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,fixtures=r['fixtures'],passing=r['passing'],
         records=r['records'],pvt=plan['pvt'],
         all_native_waveform_events_terminal=True,compiled_streaming_sequential_assessor_used=True,
         setup_hold_recovery_removal_qualified=False,numerical_domain_enclosure_qualified=False,physical_timing_qualified=False,release_qualified=False))
    save(out/'status.json',dict(state='terminal_assessment',fixtures=r['fixtures'],passing=r['passing'],
         release_qualified=False))
