"""Bounded provisional hierarchical-RC DCO pilot; parent loading and correlation remain open."""
import argparse,json,os,time
from pathlib import Path
from common import ROOT,save,sha,verify
from resources import identity,lease
from compiled_charge import execute

def run(out,corner,coarse,fine):
 if corner not in ("tt","ff","ss","sf","fs") or not 0<=coarse<=47 or not 8<=fine<=247:raise ValueError("unsupported prototype native point")
 if (corner,coarse,fine) in (("tt",1,128),("tt",1,8)):raise ValueError("existing TT reference/bracket cases must not be identically rerun")
 os.environ.update(OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',BLIS_NUM_THREADS='1')
 out.mkdir(parents=True,exist_ok=False)
 deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
 save(out/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,cpu_slots=1,memory_GiB=4,automatic_identical_retry=False))
 source=ROOT/'build/signoff400/prototype_v3_analog_reference_001';a=json.loads((source/'assessment.json').read_text())
 dco=next(r for r in a['analog_hierarchies'] if r['top'].startswith('IntegerPLL_DCO_'))
 rc=ROOT/'build/signoff400/prototype_v3_DCO_hierarchical_RC_001'
 rc_receipt=rc/'assessment.json';ca=json.loads(rc_receipt.read_text())
 if not ca.get('cell_internal_and_wire_capacitance_scopes_separated') or not ca.get('mirrored_couplings_counted_once'):raise ValueError('reviewed RC construction required')
 netlist=rc/'nom.spice'
 verify(ca['input_sha256']);verify(ca['artifacts'])
 image=ROOT/'build/apptainer/openpll-release-modern.sif';worker=ROOT/'scripts/spice_dco_postlayout_prototype_v4.py';ng=ROOT/'build/tools/ngspice47_klu_002/install/bin/ngspice'
 native=out/'native';native.mkdir();init=native/'.spiceinit';init.write_text('set ngbehavior=hsa\n')
 paths=[rc_receipt,init,source/'assessment.json',netlist,image,worker,ng,Path(__file__).resolve()];pins={str(p):sha(p) for p in paths}
 if pins[str(netlist)]!=ca['artifacts'][str(netlist)]:raise ValueError('reference hierarchy changed')
 command=['apptainer','exec','--bind','/home:/home,/tmp:/tmp',image,'/nix/store/ps0r3qpgjh1lqyqacra33rvxsjgkd874-python3-3.13.9-env/bin/python3',worker,
 '--codes',str(fine),'--coarse-codes',str(coarse),'--corner',corner,'--temperature-c','27','--vdd','1.8',
 '--pdk-root','/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae','--pdk','sky130A',
 '--rcx-netlist',netlist,'--subckt-name',dco['top'],'--build-dir',out/'native','--sim-time-ns','80','--meas-start-ns','20',
 '--step-ps','10','--max-step-ps','10','--simulator','ngspice','--ngspice',ng,'--ngspice-reltol','1e-5','--ngspice-abstol','1e-9','--ngspice-klu','--ngspice-waveform','--ngspice-threads','1','--jobs','1','--timeout-s','43000']
 save(out/'input_manifest.json',dict(input_sha256=pins,command=list(map(str,command)),diagnostic=True,corner=corner,coarse_code=coarse,fine_code=fine,interconnect_corner='nom',parent_loading_complete=False))
 try:
  save(out/'status.json',dict(state='waiting_for_reference_pilot_lease',release_ready=False))
  with lease(1,4,deadline):
   save(out/'status.json',dict(state='reference_native_pilot_running',release_ready=False))
   execute(command,out/'native.log',deadline,4)
   verify(pins)
  save(out/'assessment.json',dict(input_sha256=pins,corner=corner,coarse_code=coarse,fine_code=fine,native_worker_completed=True,diagnostic=True,final_loading_parasitics_complete=False,validated_for_prototype=False,release_ready=False,production_qualified=False))
  from assess_prototype_native_waveform import run as review
  review(out,out/'all_cycle_assessment')
  save(out/'status.json',dict(state='native_point_complete_review_pending',release_ready=False))
 except BaseException as error:
  save(out/'status.json',dict(state='stopped_without_promotion',reason=repr(error),release_ready=False));raise

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--corner',choices=('tt','ff','ss','sf','fs'),required=True);p.add_argument('--coarse',type=int,required=True);p.add_argument('--fine',type=int,required=True)
 a=p.parse_args();run(a.output.resolve(),a.corner,a.coarse,a.fine)
