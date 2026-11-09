"""Capture requested keeper coarse/fine codes with the checked BSIM backend; no band auto-selection."""
import argparse,json,os,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease
from compiled_charge_v2 import execute
from read_selected_standard import read_selected_standard as read_selected
from assess_selected_isolated_control import frequency


from contact_corrected_transient_deck import transient_deck


def run(smoke,output,fine,cpu,coarse,max_step_ps):
    if cpu not in range(32):raise ValueError("CPU must be within the declared host budget")
    receipt=smoke/'assessment.json';r=json.loads(receipt.read_text());verify(r['input_sha256']);verify(r['artifacts'])
    if not r['normal_native_exit']or not r['finite_reset_DC_point']:raise ValueError('completed checked DC reference required')
    corrected=ROOT/"build/signoff400/selected_keeper_contact_corrected_native_1579/assessment.json"
    if r["input_sha256"].get(str(corrected))!=sha(corrected):raise ValueError("corrected extraction DC lineage required")
    binary=ROOT/'build/tools/xyce_umfpack_BSIM_junction_1292/Xyce';build=binary.parent/'assessment.json';validation=ROOT/'build/signoff400/selected_keeper_corrected_BSIM_AC_1294/assessment.json';br,vr=[json.loads(p.read_text())for p in [build,validation]]
    for record in [br,vr]:verify(record['input_sha256']);verify(record['artifacts'])
    if sha(binary)!=br['binary_sha256'] or vr['input_sha256'].get(str(binary))!=sha(binary) or not vr['all_17160_current_geometry_observations_compared']:raise ValueError('corrected executable and complete geometry controls required')
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{cpu});os.environ.update(OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1');save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())));raw=output/'transient.prn';deck=output/'transient.spice';text,ports=transient_deck((smoke/'smoke.spice').read_text(),raw,fine,coarse,max_step_ps);deck.write_text(text)
    folder=Path(__file__).resolve().parent;pins={**r['input_sha256'],**{str(p):sha(p)for p in [receipt,deck,binary,Path(__file__).resolve(),folder/'run_selected_corner_initial_states.py',folder/'read_selected_standard.py',folder/'check_selected_boundary_waveforms.py',folder/'contact_corrected_transient_deck.py',folder/'run_keeper_native_BSIM_coarse_band.py',folder/'reset_contract_v4.py',folder/'requirements_v4.json',folder/'assess_selected_isolated_control.py',folder/'compiled_charge_v2.py',folder/'run_keeper_flat_native_independent.py',build,validation]}}
    verify(pins);save(output/'inputs.json',dict(input_sha256=pins,coarse=coarse,fine=fine,native_executable=str(binary),native_executable_sha256=sha(binary),BSIM_PBSWGD_default_corrected=True,all_node_voltages_requested=True,independent_resource_budgeted_case=True,legacy_full_slot_held=False,corner='tt',temperature_C=27,supply_V=1.8,PLL_ENABLE_held_low=True,contact_residue_extraction_corrected=True,capture_format="Xyce_standard_precision17",reset_release_ns=80,simulation_ns=340,max_step_ps=max_step_ps,timestep_accuracy_qualified=False,CPU=cpu,memory_GiB=16,native_cap_s=86400,max_native_cases=1,automatic_identical_retry=False,distributed_wire_R_included=False,release_ready=False))
    try:
        verify(pins);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+86400;start=time.monotonic()
        save(output/'status.json',dict(state='waiting_for_global_CPU_RAM_budget',release_ready=False))
        with lease(1,16,deadline):
            save(output/'status.json',dict(state='flat_native_programming_transient_running',release_ready=False))
            execute([binary,'-a','-linsolv','umfpack_reuse',deck],output/'native.log',deadline,16)
        verify(pins);rows=read_selected(raw,{p:p for p in ports},340e-9);window=[row for row in rows if row[0]>=280e-9];codes={};ambiguous=False
        for prefix,width in [('COARSE_CODE',6),('DCO_CODE',8)]:
            observed=set()
            for row in window:
                value=0
                for i in range(width):
                    v=row[1+ports.index(f'{prefix}[{i}]')];ambiguous|=.36<v<1.44
                    if v>=.9:value|=1<<i
                observed.add(value)
            codes[prefix]=sorted(observed)
        stationary=codes=={'COARSE_CODE':[coarse],'DCO_CODE':[fine]}and not ambiguous
        measured=None;frequency_reason=None
        if stationary:
            try:measured=frequency(rows,280,340)
            except ValueError as e:frequency_reason=str(e)
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p)for p in [deck,raw,output/'native.log']},normal_native_completion=True,native_executable=str(binary),native_executable_sha256=sha(binary),BSIM_PBSWGD_default_corrected=True,all_saved_native_values_finite=True,all_node_voltages_requested=True,requested_coarse=coarse,requested_fine=fine,max_step_ps=max_step_ps,elapsed_s=time.monotonic()-start,window_ns=[280,340],codes=codes,ambiguous_code_voltage=ambiguous,stationary_requested_code=stationary,frequency_diagnostic=measured,frequency_unavailable_reason=frequency_reason,distributed_wire_R_included=False,transient_correlation_qualified=False,model_qualified=False,release_ready=False));save(output/'status.json',dict(state='flat_native_programming_transient_complete',release_ready=False))
    except BaseException as e:save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--smoke',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--fine',type=int,required=True);p.add_argument('--cpu',type=int,required=True);p.add_argument('--coarse',type=int,required=True);p.add_argument('--max-step-ps',type=int,choices=[10,50],required=True);a=p.parse_args();run(a.smoke.resolve(),a.output.resolve(),a.fine,a.cpu,a.coarse,a.max_step_ps)
