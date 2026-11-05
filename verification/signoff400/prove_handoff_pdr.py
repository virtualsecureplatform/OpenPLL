"""Independent AIG/PDR proof of the same 34-bit, two-clock sampled contract."""
from datetime import datetime,timezone
import argparse
import hashlib,json,os
from pathlib import Path
import subprocess,sys,time
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'verification/signoff400'))
from common import save,sha,verify,source_pins,PROFILE
from prove_handoff_v2 import instrument,MUTANTS,YOSYS
sys.path.append(str(ROOT/'verification/prototype400'))
from parallel_geometry_jobs import run_jobs
ABC=str(Path(YOSYS).with_name('yosys-abc'))
def run(output,container,workers=4):
 OUT=Path(output).resolve();OUT.mkdir(parents=True,exist_ok=False)
 IMAGE=Path(container).resolve();PREFIX=['apptainer','exec','--bind','/home:/home,/tmp:/tmp',str(IMAGE)]
 started=time.clock_gettime(time.CLOCK_BOOTTIME);deadline=started+43200
 rtl=ROOT/'rtl/prototype400/IntegerPLL_TuningHandoff.v';prop=ROOT/'verification/signoff400/handoff_properties.vh'
 pins=dict(source_pins(),**{str(p):sha(p) for p in [Path(__file__).resolve(),Path(sys.executable),rtl,prop,IMAGE,ROOT/'verification/signoff400/prove_handoff_v2.py',ROOT/'verification/signoff400/common.py',ROOT/'verification/prototype400/parallel_geometry_jobs.py',ROOT/'verification/signoff400/resources.py',Path('/usr/bin/prlimit')]})
 save(OUT/'owner.json',dict(pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),wall_limit_s=43200,automatic_identical_retry=False,algorithm='AIGER_constraints_folded_then_IC3_PDR',workers=workers,per_case_memory_GiB=4))
 def status(state,**kw):save(OUT/'status.json',dict(state=state,observed_utc=datetime.now(timezone.utc).isoformat(),release_qualified=False,**kw))
 try:
  properties=prop.read_text();source=rtl.read_text()
  cases={name:(instrument(source,properties,name if name in MUTANTS else None),'IntegerPLL_TuningHandoff',name=='baseline') for name in ('baseline',*MUTANTS)}
  changed=properties.replace('if (f_previous_ref_reset && !REF_RESET_N) assume(!DCO_RESET_N);','').replace('if (f_previous_dco_reset && !DCO_RESET_N) assume(!REF_RESET_N);','')
  cases['reset_contract_removed']=(instrument(source,changed),'IntegerPLL_TuningHandoff',False)
  witness=properties.split('reg f_ref_valid;')[0].replace('assert(!APPLIED || (REF_RESET_N && DCO_RESET_N && APPLIED_COMMAND == COMMAND));','assert(!APPLIED);')
  cases['transfer_reachable']=(instrument(source,witness),'IntegerPLL_TuningHandoff',False)
  cases['engine_constraint_control']=('module tiny(input clk,cmd);reg q=0;always @(posedge clk) q<=cmd;always @($global_clock) begin assume(!cmd);assert(!q);end endmodule','tiny',True)
  cases['engine_counterexample_control']=('module tiny(input clk,cmd);reg q=0;always @(posedge clk) q<=cmd;always @($global_clock) assert(!q);endmodule','tiny',False)
  cases['engine_unknown_initial_control']=('module tiny(input clk);reg q;always @(posedge clk) q<=0;always @($global_clock) assert(!q);endmodule','tiny',False)
  exports=[]
  for name,(text,top,expected) in cases.items():
   folder=OUT/name;folder.mkdir();design=folder/'model.v';design.write_text(text)
   param='chparam -set WIDTH 34 -set APPLY_CYCLES 3 IntegerPLL_TuningHandoff\n' if top!='tiny' else ''
   recipe=folder/'export.ys';recipe.write_text(f'read_verilog -formal -sv {design}\n'+param+f'prep -top {top}\nclk2fflogic\nopt\ndelete -output\nflatten\ntechmap\nopt\naigmap\nopt_clean\nwrite_aiger -zinit -symbols -map {folder}/model.map {folder}/model.aig\n')
   pins.update({str(path):sha(path) for path in (design,recipe)})
   exports.append(dict(label=name,command=PREFIX+[YOSYS,'-s',str(recipe)],cpus=1,memory_gib=4))
  run_jobs(exports,OUT,pins,deadline,workers=workers,update=lambda **kw:status('exporting_controlled_AIG_models',**kw))
  headers={}
  for name in cases:
   model=OUT/name/'model.aig'
   with model.open('rb') as stream:tokens=stream.readline().decode().split()
   if tokens[0]!='aig':raise ValueError('unexpected AIGER format')
   fields=list(map(int,tokens[1:]));fields += [0]*(9-len(fields))
   expected_bad=6 if name in ('baseline',*MUTANTS,'reset_contract_removed') else 1
   expected_constraints=3 if name in ('baseline',*MUTANTS,'transfer_reachable') else (1 if name in ('reset_contract_removed','engine_constraint_control') else 0)
   if fields[3]!=0 or fields[5]!=expected_bad or fields[6]!=expected_constraints:
    raise ValueError('AIGER property/constraint inventory mismatch: '+name)
   headers[name]=dict(inputs=fields[1],latches=fields[2],regular_outputs=fields[3],assertions=fields[5],constraints=fields[6])
   pins[str(model)]=sha(model)
   pins[str(OUT/name/'model.map')]=sha(OUT/name/'model.map')
  save(OUT/'input_manifest.json',dict(input_sha256=pins))
  save(OUT/'aiger_inventory.json',headers)
  jobs=[dict(label=name,command=PREFIX+[ABC,'-c',f'read_aiger {OUT/name}/model.aig; fold; strash; pdr -v -d -I {OUT/name}/invariant.pla -T 3600'],cpus=1,memory_gib=4,allow_nonzero=True) for name in cases]
  engine=OUT/'engine';engine.mkdir()
  results=run_jobs(jobs,engine,pins,deadline,workers=workers,update=lambda **kw:status('parallel_PDR_running',**kw))
  records=[]
  for name,(_,_,expected) in cases.items():
   log=(engine/(name+'.log')).read_text();safe='Property proved' in log;unsafe='was asserted in frame' in log
   records.append(dict(case=name,expected_safe=expected,native_exit=results[name],safe=safe,unsafe=unsafe))
  save(OUT/'case_results.json',records)
  if not all(r['native_exit']==0 and ((r['safe'] and not r['unsafe']) if r['expected_safe'] else (r['unsafe'] and not r['safe'])) for r in records):raise RuntimeError('PDR result or engine control nonpass')
  verify(pins)
  save(OUT/'assessment.json',dict(profile_sha256=sha(PROFILE),candidate_source_sha256=source_pins(),input_sha256=pins,artifacts={str(p):sha(p) for p in OUT.rglob('*') if p.is_file() and p.name not in ('assessment.json','status.json','driver.log')},records=records,aiger_inventory=headers,handoff_width=34,apply_cycles=3,assumptions=['both resets initially asserted','subsequent reset assertions occur together','reset releases may differ; clocks can stall or change independently','discrete RTL clock samples, without analog or metastability modeling'],sampled_handoff_safety_proven=True,all_three_negative_controls_rejected=True,reset_assertion_contract_negative_control_rejected=True,successful_transfer_reachable=True,independent_constraint_and_unknown_initial_state_controls_passed=True,digital_startup_qualified=False,interface_model_qualified=False,physical_timing_qualified=False,release_qualified=False,scope='Sampled two-clock handoff safety only; no metastability, payload-delay, reset recovery or integrated-startup qualification',elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-started))
  status('sampled_handoff_safety_proven_pending_physical_and_integration_bounds')
 except BaseException as error:status('failed',reason=repr(error));raise
if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--output',required=True,type=Path);parser.add_argument('--container',required=True,type=Path)
 parser.add_argument('--jobs',type=int,choices=(1,2,4),default=4)
 a=parser.parse_args();run(a.output,a.container,a.jobs)
