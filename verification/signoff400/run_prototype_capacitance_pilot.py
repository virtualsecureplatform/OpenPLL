"""Bounded isolated-capacitance DCO pilot; parent loading and distributed R remain open."""
import json,os,time
from pathlib import Path
from common import ROOT,save,sha,verify
from resources import identity,lease
from compiled_charge import execute

def run():
 os.environ.update(OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',BLIS_NUM_THREADS='1')
 out=ROOT/'build/signoff400/prototype_v3_TT_capacitance_pilot_001';out.mkdir(exist_ok=False)
 deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
 save(out/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,cpu_slots=1,memory_GiB=16,automatic_identical_retry=False))
 source=ROOT/'build/signoff400/prototype_v3_analog_reference_001';a=json.loads((source/'assessment.json').read_text())
 dco=next(r for r in a['analog_hierarchies'] if r['top'].startswith('IntegerPLL_DCO_'))
 cap=ROOT/'build/signoff400/prototype_v3_analog_capacitance_002';cap_receipt=cap/'native_assessment.json';ca=json.loads(cap_receipt.read_text())
 devices=ROOT/'build/signoff400/prototype_v3_analog_device_comparison_002/assessment.json';passivity=ROOT/'build/signoff400/prototype_v3_analog_capacitance_passivity_001/assessment.json'
 if json.loads(devices.read_text()).get('all_expanded_primitive_cards_match') is not True or json.loads(passivity.read_text()).get('extracted_capacitor_networks_passive') is not True:raise ValueError('matching devices and passive capacitor networks required')
 netlist=cap/dco['top']/'capacitance.spice'
 image=ROOT/'build/apptainer/openpll-release-modern.sif';worker=ROOT/'scripts/spice_dco_postlayout.py';ng=ROOT/'build/tools/ngspice47/install/bin/ngspice'
 native=out/'native';native.mkdir();init=native/'.spiceinit';init.write_text('set ngbehavior=hsa\n')
 paths=[cap_receipt,devices,passivity,init,source/'assessment.json',netlist,image,worker,ng,Path(__file__).resolve()];pins={str(p):sha(p) for p in paths}
 if pins[str(netlist)]!=ca['artifacts'][str(netlist)]:raise ValueError('reference hierarchy changed')
 command=['apptainer','exec','--bind','/home:/home,/tmp:/tmp',image,'/nix/store/ps0r3qpgjh1lqyqacra33rvxsjgkd874-python3-3.13.9-env/bin/python3',worker,
 '--codes','128','--coarse-codes','1','--corner','tt','--temperature-c','27','--vdd','1.8',
 '--pdk-root','/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae','--pdk','sky130A',
 '--rcx-netlist',netlist,'--subckt-name',dco['top'],'--build-dir',out/'native','--sim-time-ns','80','--meas-start-ns','20',
 '--step-ps','10','--max-step-ps','10','--simulator','ngspice','--ngspice',ng,'--ngspice-threads','1','--jobs','1','--timeout-s','43000']
 save(out/'input_manifest.json',dict(input_sha256=pins,command=list(map(str,command)),reference_only=True))
 try:
  save(out/'status.json',dict(state='waiting_for_reference_pilot_lease',release_ready=False))
  with lease(1,16,deadline):
   save(out/'status.json',dict(state='reference_native_pilot_running',release_ready=False))
   execute(command,out/'native.log',deadline,16)
   verify(pins)
  save(out/'assessment.json',dict(input_sha256=pins,native_worker_completed=True,diagnostic=True,final_loading_parasitics_complete=False,validated_for_prototype=False,release_ready=False,production_qualified=False))
  save(out/'status.json',dict(state='reference_pilot_terminal_review_native_metrics',release_ready=False))
 except BaseException as error:
  save(out/'status.json',dict(state='stopped_without_promotion',reason=repr(error),release_ready=False));raise

if __name__=='__main__':run()
