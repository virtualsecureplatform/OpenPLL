import json,os,subprocess,sys,time
from pathlib import Path
sys.path.insert(0,str(Path('verification/signoff400').resolve()))
from common_v3 import ROOT,save,sha,verify
from resources import identity
phase=float(sys.argv[1]);cpu=int(sys.argv[2]);number=sys.argv[3]
output=ROOT/f'build/signoff400/selected_detector_recorded_sync_clock_case_{number}';output.mkdir(exist_ok=False)
runner=ROOT/'verification/signoff400/run_selected_detector_phase_probe_v8.py';assessor=ROOT/'verification/signoff400/assess_selected_detector_phase_probe_v3.py';characterizer=ROOT/'verification/signoff400/characterize_selected_detector_response_v2.py'
pins={str(p):sha(p) for p in [Path(__file__),runner,assessor,characterizer]}
save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
probe=output/'native';assessment=output/'waveform_assessment';ports=ROOT/'build/signoff400/selected_detector_physical_wire_ports_182.json'
command=['apptainer','exec','--bind','/home:/home,/tmp:/tmp',ROOT/'build/apptainer/openpll-release-modern.sif','/usr/bin/python3',runner,'--plan',ROOT/'build/signoff400/selected_real_feedback_driver_loaded_detector_cut_267/plan.json','--stimuli',ROOT/'build/signoff400/selected_real_feedback_driver_loaded_detector_cut_267/stimulus_ports.json','--model',ROOT/'build/signoff400/prototype_v3_Xyce_full_C_programming_pilot_030/model.spice','--native',ROOT/'build/signoff400/prototype_v3_loaded_startup_260ns_131','--output',probe,'--phase-ns',str(phase),'--cpu',str(cpu),'--initial-snapshot',ROOT/'build/signoff400/selected_full_initial_voltage_snapshot_216','--detector-ports',ports,'--clock-waveforms',ROOT/'build/signoff400/selected_interface_clock_reset_waveforms_278']
save(output/'manifest.json',dict(input_sha256=pins,command=list(map(str,command)),CPU=cpu,memory_GiB=12,automatic_identical_retry=False,release_ready=False))
try:
 verify(pins);save(output/'status.json',dict(state='running_nearzero_native_probe',release_ready=False))
 with (output/'probe.log').open('x') as log:subprocess.run(list(map(str,command)),check=True,stdout=log,stderr=subprocess.STDOUT,timeout=12600)
 verify(pins);save(output/'status.json',dict(state='assessing_nearzero_probe',release_ready=False))
 with (output/'assessment.log').open('x') as log:subprocess.run([sys.executable,str(assessor),'--probe',str(probe),'--ports',str(ports),'--inventory',str(ROOT/'build/signoff400/selected_detector_boundary_inventory_181.json'),'--output',str(assessment)],check=True,stdout=log,stderr=subprocess.STDOUT,timeout=1200)
 with (output/'response.log').open('x') as log:subprocess.run([sys.executable,str(characterizer),'--assessment',str(assessment/'assessment.json'),'--receivers',str(ROOT/'build/signoff400/selected_detector_receiver_inventory_186.json'),'--output',str(output/'response.json')],check=True,stdout=log,stderr=subprocess.STDOUT,timeout=300)
 verify(pins);save(output/'status.json',dict(state='nearzero_conditional_response_measured',release_ready=False))
except BaseException as error:
 save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise
