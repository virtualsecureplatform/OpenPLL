"""Rebuild conservative tracking models and bind identical existing proof artifacts to keeper RTL."""
import argparse,json,os,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import lease,identity
from compiled_charge_v2 import execute
from prove_handoff_v2 import YOSYS
from prove_prototype_tracking_configuration_stability_v2 import instrument


def run(route,proof,reachability,output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{28});save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())));os.environ.update(GOMAXPROCS='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    try:
        rr,br=[p/'assessment.json' for p in [route,reachability]];r,b=[json.loads(p.read_text()) for p in [rr,br]]
        verify(b['input_sha256']);verify(b['artifacts'])
        if not b['baseline_joint_assertions_proved'] or not b['tracked_configuration_state_reachable'] or not b['only_stability_assertion_inverted'] or not b['conservative_core_cut_retained']:raise ValueError('completed induction and nonvacuity control required')
        if 'Property proved.' not in (proof/'baseline/proof.log').read_text() or 'was asserted in frame' not in (reachability/'bmc.log').read_text():raise ValueError('native completed proof and reachability logs required')
        source_paths=sorted(Path(p) for p in r['candidate_source_sha256'] if p.endswith('.v'))
        if len(source_paths)!=9:raise ValueError('nine current route sources required')
        source_pins={str(p):r['candidate_source_sha256'][str(p)] for p in source_paths};verify(source_pins)
        if any(r['input_sha256'].get(p)!=h for p,h in source_pins.items()):raise ValueError('current route declared source mismatch')
        programmed=next(p for p in source_paths if p.name=='IntegerPLL_ProgrammedCore.v');pins={**source_pins,**{str(p):sha(p) for p in [rr,br,Path(__file__).resolve(),Path(__file__).with_name('prove_prototype_tracking_configuration_stability_v2.py'),Path(YOSYS)]}};artifacts={};results=[]
        save(output/'inputs.json',dict(input_sha256=pins,memory_GiB=2,CPU=28,resource_queue_cap_s=7200,native_campaign_cap_s=600,maximum_model_exports=2,existing_native_proof_reused=True,release_ready=False));save(output/'status.json',dict(state='waiting_for_global_CPU_RAM_budget',release_ready=False))
        with lease(1,2,time.clock_gettime(time.CLOCK_BOOTTIME)+7200):
            deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+600
            for name,mutant in [('baseline',False),('tracking_reachability_control',True)]:
                old=proof/name;design=old/'IntegerPLL_ProgrammedCore.v'
                if design.read_text()!=instrument(programmed.read_text(),mutant):raise ValueError('current RTL does not reconstruct the recorded conservative cut')
                script=old/'export.ys';text=script.read_text();first=text.splitlines()[0].split()
                expected={str(design),*[str(p) for p in source_paths if p!=programmed]}
                if first[:3]!=['read_verilog','-formal','-sv'] or set(first[3:])!=expected or len(first[3:])!=9:raise ValueError('formal export reads a different current source set')
                expected_model=b['input_sha256'].get(str(old/'model.aig'))
                if expected_model is None or sha(old/'model.aig')!=expected_model:raise ValueError('recorded formal model not pinned by completed proof control')
                target=output/name;target.mkdir();model=target/'model.aig';recipe=target/'export.ys';recipe.write_text(text.replace(str(old/'model.map'),str(target/'model.map')).replace(str(old/'model.aig'),str(model)))
                pins.update({str(p):sha(p) for p in [design,script,old/'model.aig',recipe]});verify(pins);save(output/'status.json',dict(state='rebuilding_current_route_formal_model',case=name,release_ready=False));execute([YOSYS,'-s',recipe],target/'export.log',deadline,2)
                actual=sha(model)
                if actual!=expected_model:raise ValueError('current source elaboration differs from the recorded formal model')
                results.append(dict(case=name,reconstructed_AIG_sha256=actual,recorded_AIG_sha256=expected_model,exact_match=True));artifacts.update({str(p):sha(p) for p in target.iterdir() if p.is_file()})
        verify(pins);save(output/'assessment.json',dict(input_sha256={**b['input_sha256'],**pins},artifacts=artifacts,results=results,current_route_declared_RTL_formal_models_reconstructed_exactly=True,configuration_stable_during_sampled_tracking_proved=True,ready_configuration_and_running_fine_payload_match_static_presets_proved=True,tracked_configuration_state_reachable=True,existing_induction_and_BMC_control_reused=True,new_induction_run_performed=False,conservative_free_core_outputs_and_feedback_clock_cut=True,initial_seed_loading_proved=False,full_core_behavior_proved=False,assumptions=['RESET_N asserted for first two global samples','presets and gains stable between external resets','ideal sampled RTL clocks; no analog metastability model'],routed_netlist_equivalence_qualified=False,physical_timing_qualified=False,release_ready=False));save(output/'status.json',dict(state='current_route_tracking_formal_models_bound',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ['route','proof','reachability','output']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(a.route.resolve(),a.proof.resolve(),a.reachability.resolve(),a.output.resolve())
