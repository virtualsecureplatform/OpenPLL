"""Run one next-stage native control and assess all complete saved observations."""
import argparse,json,os,subprocess,sys
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity


def run(plan,waveforms,output,phase,cpu):
    output.mkdir(parents=True,exist_ok=False)
    folder=Path(__file__).resolve().parent;image=ROOT/'build/apptainer/openpll-release-modern.sif'
    runner=folder/'run_selected_detector_phase_probe_v10.py';assessor=folder/'assess_selected_detector_phase_probe_v4.py'
    pins={str(p):sha(p) for p in [Path(__file__).resolve(),runner,assessor,plan/'plan.json',plan/'stimulus_ports.json',waveforms/'assessment.json']};verify(pins)
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    command=['apptainer','exec','--bind',f'{ROOT}:{ROOT}',image,'/usr/bin/python3',runner,
        '--plan',plan/'plan.json','--stimuli',plan/'stimulus_ports.json',
        '--model',ROOT/'build/signoff400/prototype_v3_Xyce_full_C_programming_pilot_030/model.spice',
        '--native',ROOT/'build/signoff400/prototype_v3_loaded_startup_260ns_131','--output',output/'native',
        '--phase-ns',phase,'--cpu',cpu,'--initial-snapshot',ROOT/'build/signoff400/selected_full_initial_voltage_snapshot_216',
        '--detector-ports',ROOT/'build/signoff400/selected_detector_physical_wire_ports_182.json','--clock-waveforms',waveforms]
    save(output/'manifest.json',dict(input_sha256=pins,command=list(map(str,command)),CPU=cpu,automatic_identical_retry=False,release_ready=False))
    try:
        save(output/'status.json',dict(state='second_stage_native_running',release_ready=False))
        with (output/'native.log').open('x') as log:subprocess.run(list(map(str,command)),stdout=log,stderr=subprocess.STDOUT,check=True,timeout=12600)
        verify(pins)
        command=[sys.executable,assessor,'--probe',output/'native','--ports',ROOT/'build/signoff400/selected_detector_physical_wire_ports_182.json','--inventory',ROOT/'build/signoff400/selected_detector_boundary_inventory_181.json','--output',output/'waveform_assessment']
        with (output/'assessment.log').open('x') as log:subprocess.run(list(map(str,command)),stdout=log,stderr=subprocess.STDOUT,check=True,timeout=1200)
        verify(pins);save(output/'status.json',dict(state='recorded_phase_response_measured',second_stage_observed=True,full_controller_timing_qualified=False,release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['plan','waveforms','output']:p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--phase-ns',type=float,required=True);p.add_argument('--cpu',type=int,required=True,choices=range(16,32))
    a=p.parse_args();run(a.plan.resolve(),a.waveforms.resolve(),a.output.resolve(),a.phase_ns,a.cpu)
