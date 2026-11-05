"""Full-duration diagnostic of a certified single-map C attachment; exterior loading remains open."""
import argparse,json,os,time
from pathlib import Path
from common import ROOT,save,sha,verify
from resources import identity,lease
from compiled_charge import execute

def run(out,corner,coarse,fine,rc,candidate,attachment,deadline_owner):
 if corner not in ("tt","ff","ss","sf","fs") or not 0<=coarse<=47 or not 8<=fine<=247:raise ValueError("unsupported prototype native point")
 os.environ.update(GOMAXPROCS='1',OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',BLIS_NUM_THREADS='1')
 out.mkdir(parents=True,exist_ok=False)
 deadline=json.loads(deadline_owner.read_text())['deadline_uptime']
 if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('original checkpoint deadline expired')
 save(out/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,cpu_slots=1,memory_GiB=16,automatic_identical_retry=False))
 source=candidate; a=json.loads((source/'assessment.json').read_text());verify(a['input_sha256']);verify(a['artifacts'])
 dco=dict(top=next(Path(p).stem for p in a['artifacts'] if p.endswith('.gds')))
 rc_receipt=rc/'assessment.json';ca=json.loads(rc_receipt.read_text())
 if not ca.get('all_geometric_interactions_retained') or not ca.get('zero_wire_R_topology_and_capacitance_operator_identity_verified'):raise ValueError('complete geometric C and contraction checks required')
 if not ca.get('capacitance_lifts_are_exact_matrix_congruences') or not ca.get('each_fixed_supply_dynamic_C_operator_passivity_certified'):raise ValueError('single voltage-map congruence and exact fixed-supply certificates required')
 if attachment not in ('driver','farthest'):raise ValueError('explicit placement variant required')
 if not ca.get('candidate_gds_sha256') or any(a['artifacts'].get(p)!=h for p,h in ca['candidate_gds_sha256'].items()):raise ValueError('RC model and candidate GDS differ')
 netlist=rc/(attachment+'.spice')
 verify(ca['input_sha256']);verify(ca['artifacts'])
 image=ROOT/'build/apptainer/openpll-release-modern.sif';worker=ROOT/'scripts/spice_dco_postlayout_prototype_v6.py';ng=ROOT/'build/tools/ngspice47_klu_002/install/bin/ngspice'
 power_control=ROOT/'build/signoff400/prototype_v3_supply_measurement_control_v6_001/assessment.json'
 control=json.loads(power_control.read_text());verify(control['input_sha256']);verify(control['artifacts'])
 if not control['supply_current_sign_units_and_both_rails_verified'] or control['input_sha256'].get(str(worker))!=sha(worker):raise ValueError('matching native power measurement control required')
 native=out/'native';native.mkdir();init=native/'.spiceinit';init.write_text('set ngbehavior=hsa\n')
 paths=[deadline_owner,power_control,rc_receipt,init,source/'assessment.json',netlist,image,worker,ng,Path(__file__).resolve()]
 paths.extend(Path(p) for p in a['artifacts'] if p.endswith('.gds'));pins={str(p):sha(p) for p in paths}
 if pins[str(netlist)]!=ca['artifacts'][str(netlist)]:raise ValueError('reference hierarchy changed')
 command=['apptainer','exec','--bind','/home:/home,/tmp:/tmp',image,'/nix/store/ps0r3qpgjh1lqyqacra33rvxsjgkd874-python3-3.13.9-env/bin/python3',worker,
 '--codes',str(fine),'--coarse-codes',str(coarse),'--corner',corner,'--temperature-c','27','--vdd','1.8',
 '--pdk-root','/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae','--pdk','sky130A',
 '--rcx-netlist',netlist,'--subckt-name',dco['top'],'--build-dir',out/'native','--sim-time-ns','80','--meas-start-ns','20',
 '--step-ps','10','--max-step-ps','10','--simulator','ngspice','--ngspice',ng,'--ngspice-reltol','1e-5','--ngspice-abstol','1e-9','--ngspice-klu','--ngspice-waveform','--ngspice-threads','1','--jobs','1','--timeout-s','43000']
 save(out/'input_manifest.json',dict(input_sha256=pins,command=list(map(str,command)),diagnostic=True,band_probe_only=False,full_geometric_C_attachment=attachment,simulation_time_ns=80,measurement_start_ns=20,corner=corner,coarse_code=coarse,fine_code=fine,interconnect_corner='nom',parent_loading_complete=False))
 try:
  save(out/'status.json',dict(state='waiting_for_reference_pilot_lease',release_ready=False))
  with lease(1,16,deadline):
   save(out/'status.json',dict(state='reference_native_pilot_running',release_ready=False))
   execute(command,out/'native.log',deadline,16)
   verify(pins)
  save(out/'assessment.json',dict(input_sha256=pins,corner=corner,coarse_code=coarse,fine_code=fine,native_worker_completed=True,diagnostic=True,band_probe_only=False,full_geometric_C_attachment=attachment,simulation_time_ns=80,measurement_start_ns=20,final_loading_parasitics_complete=False,validated_for_prototype=False,release_ready=False,production_qualified=False))
  from assess_prototype_native_waveform import run as review
  review(out,out/'all_cycle_assessment')
  from review_prototype_DCO_supply_power import run as power_review
  power_review(out,out/'supply_power_assessment')
  save(out/'status.json',dict(state='native_point_complete_review_pending',release_ready=False))
 except BaseException as error:
  save(out/'status.json',dict(state='stopped_without_promotion',reason=repr(error),release_ready=False));raise

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--corner',choices=('tt','ff','ss','sf','fs'),required=True);p.add_argument('--coarse',type=int,required=True);p.add_argument('--fine',type=int,required=True)
 p.add_argument('--rc',type=Path,required=True);p.add_argument('--candidate',type=Path,required=True)
 p.add_argument('--deadline-owner',type=Path,required=True)
 p.add_argument('--attachment',required=True,choices=('driver','farthest'));a=p.parse_args();run(a.output.resolve(),a.corner,a.coarse,a.fine,a.rc.resolve(),a.candidate.resolve(),a.attachment,a.deadline_owner.resolve())
