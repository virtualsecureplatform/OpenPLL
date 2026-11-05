"""Run and measure one physical-driver detector case in the pinned container.

All phases use the same recorded native input packet and real Q driver. No
response or reference/feedback edge pairing is presumed. Diagnostic only.
"""
import argparse,json,os,subprocess,sys,math
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity


def run(phase,cpu,output,corner,initial_snapshot):
    if not math.isfinite(phase) or not -7<=phase<=30:raise ValueError('covered recorded phase coordinate required')
    if corner not in ['ff','ss','sf','fs']:raise ValueError('non-TT process corner required')
    os.sched_setaffinity(0,{cpu});output.mkdir(parents=True,exist_ok=False)
    folder=Path(__file__).resolve().parent
    runner=folder/'run_selected_detector_phase_probe_v9.py'
    assessor=folder/'assess_selected_detector_phase_probe_v4.py'
    characterizer=folder/'characterize_selected_detector_response_v3.py'
    image=ROOT/'build/apptainer/openpll-release-modern.sif'
    ports=ROOT/'build/signoff400/selected_detector_physical_wire_ports_182.json'
    probe=output/'native';assessment=output/'waveform_assessment'
    paths=[Path(__file__).resolve(),runner,assessor,characterizer,image]
    pins={str(p):sha(p) for p in paths};verify(pins)
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    command=['apptainer','exec','--bind',f'{ROOT}:{ROOT}',image,'/usr/bin/python3',runner,
        '--plan',ROOT/'build/signoff400/selected_real_feedback_driver_loaded_detector_cut_267/plan.json',
        '--stimuli',ROOT/'build/signoff400/selected_real_feedback_driver_loaded_detector_cut_267/stimulus_ports.json',
        '--model',ROOT/'build/signoff400/prototype_v3_Xyce_full_C_programming_pilot_030/model.spice',
        '--native',ROOT/'build/signoff400/prototype_v3_loaded_startup_260ns_131',
        '--output',probe,'--phase-ns',str(phase),'--cpu',str(cpu),
        '--initial-snapshot',initial_snapshot,'--corner',corner,
        '--detector-ports',ports,'--clock-waveforms',ROOT/'build/signoff400/selected_interface_clock_reset_waveforms_278']
    save(output/'manifest.json',dict(input_sha256=pins,command=list(map(str,command)),CPU=cpu,memory_GiB=12,
         phase_ns=phase,corner=corner,upstream_waveforms_corner='tt',corner_sender_waveforms_correlated=False,automatic_identical_retry=False,reference_rise_target_ns=20,release_ready=False))
    try:
        save(output/'status.json',dict(state='corner_detector_native_running',release_ready=False))
        with (output/'probe.log').open('x') as log:
            subprocess.run(list(map(str,command)),check=True,stdout=log,stderr=subprocess.STDOUT,timeout=12600)
        verify(pins)
        save(output/'status.json',dict(state='assessing_corner_detector_response',release_ready=False))
        with (output/'assessment.log').open('x') as log:
            subprocess.run(list(map(str,[sys.executable,assessor,'--probe',probe,'--ports',ports,
                '--inventory',ROOT/'build/signoff400/selected_detector_boundary_inventory_181.json',
                '--output',assessment])),check=True,stdout=log,stderr=subprocess.STDOUT,timeout=1200)
        with (output/'response.log').open('x') as log:
            subprocess.run(list(map(str,[sys.executable,characterizer,'--assessment',assessment/'assessment.json',
                '--receivers',ROOT/'build/signoff400/selected_detector_receiver_inventory_186.json',
                '--output',output/'response.json'])),check=True,stdout=log,stderr=subprocess.STDOUT,timeout=300)
        verify(pins)
        save(output/'status.json',dict(state='corner_detector_response_measured',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--phase-ns',type=float,required=True)
    parser.add_argument('--cpu',type=int,choices=range(16,32),required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--corner',choices=['ff','ss','sf','fs'],required=True)
    parser.add_argument('--initial-snapshot',type=Path,required=True)
    args=parser.parse_args();run(args.phase_ns,args.cpu,args.output.resolve(),args.corner,args.initial_snapshot.resolve())
