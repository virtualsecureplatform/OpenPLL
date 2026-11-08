"""Controlled reduced replay with current-type LTE masking and local native output."""
import os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',LC_ALL='C')
import argparse,json,time,tempfile,shutil
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease
from retain_completed_native_trace import retain
from extract_keeper_replay_waveforms import run as extract_run,completed_reference
from write_keeper_tablefile_sources import run as sources_run
from compiled_charge_v2 import execute
from assess_selected_detector_phase_probe_v2 import read_selected
from assess_selected_isolated_control import frequency

from queue_keeper_conditional_replay import replay_deck

def checked_backend(record,expected_hash):
    binary=str(ROOT/'build/tools/xyce_umfpack_value_gather_001/Xyce')
    candidates={p:h for p,h in record.get('input_sha256',{}).items() if p.endswith('/Xyce')}
    if candidates!={binary:expected_hash}:raise ValueError('one matching pinned old active backend required')


def run(reference,conditional,plan,physical,original_waveforms,reduction,waveforms,staging,output):
    receipts=[p/'assessment.json' for p in [conditional,plan]];c,p=[json.loads(q.read_text()) for q in receipts]
    for r in [c,p]:verify(r['input_sha256']);verify(r['artifacts'])
    if p['input_sha256'].get(str(receipts[0]))!=sha(receipts[0]):raise ValueError('plan belongs to another conditional model')
    if not c['PLLOUT_not_externally_driven'] or not p['PLLOUT_forcing_forbidden']:raise ValueError('checked free-output preparations required')
    reduction_receipt=reduction/'assessment.json';reduced=json.loads(reduction_receipt.read_text());verify(reduced['input_sha256']);verify(reduced['artifacts'])
    reduced_bindings=json.loads((reduction/'bindings.json').read_text())
    if reduced['input_sha256'].get(str(receipts[0]))!=sha(receipts[0]) or not reduced['symbolic_retained_charge_coefficients_preserved'] or reduced['native_equivalence_verified'] or reduced['native_simulation_allowed']:raise ValueError('matching explicitly unqualified symbolic reduction required')
    binary=ROOT/'build/tools/xyce_umfpack_value_gather_001/Xyce';backend_hash=sha(binary);reference_inputs=reference/'inputs.json';ri=json.loads(reference_inputs.read_text());checked_backend(ri,backend_hash);verify(ri['input_sha256'])
    physical_plan=physical/'plan.json';pp=json.loads(physical_plan.read_text());verify(pp['input_sha256'])
    if pp['input_sha256'].get(str(reference_inputs))!=sha(reference_inputs) or (ri['corner'],ri['temperature_C'],ri['supply_V'],ri['max_step_ps'],ri['simulation_ns'])!=('tt',27,1.8,50,260) or not ri['all_node_voltages_requested']:raise ValueError('matching physical plan and full 50 ps TT capture required')
    controls=ROOT/'build/signoff400/selected_xyce_shared_TABLEFILE_controls_1375/assessment.json';cr=json.loads(controls.read_text());verify(cr['input_sha256']);verify(cr['artifacts'])
    if not cr['all_twelve_native_controls_complete'] or not cr['literal_source_samples_and_knot_breakpoints_verified'] or not cr['shared_knot_driver_used']:raise ValueError('complete native TABLEFILE controls required')
    mask_controls=ROOT/'build/signoff400/selected_capacitor_boundary_MASKIVARS_controls_1409/assessment.json';mc=json.loads(mask_controls.read_text());verify(mc['input_sha256']);verify(mc['artifacts'])
    if not mc['all_twenty_four_native_RC_controls_complete'] or not mc['current_type_variables_masked_from_LTE'] or not mc['voltage_LTE_control_retained'] or mc['input_sha256'].get(str(binary))!=backend_hash:raise ValueError('completed matching voltage-LTE RC controls required')
    owner_file=reference/'owner.json';owner=json.loads(owner_file.read_text());folder=Path(__file__).resolve().parent
    files=[mask_controls,reduction_receipt,reduction/'model.spice',reduction/'bindings.json',reduction/'charge_certificate.json',original_waveforms/'assessment.json',staging/'owner.json',controls,waveforms/'assessment.json',Path('/usr/bin/time'),*receipts,owner_file,reference_inputs,binary,physical/'owner.json',physical/'plan.json',conditional/'model.spice',conditional/'bindings.json',plan/'ports.json',Path(__file__).resolve(),*[folder/n for n in ['extract_keeper_replay_waveforms.py','write_keeper_tablefile_sources.py','plan_keeper_conditional_replay.py','compiled_charge_v2.py','assess_selected_detector_phase_probe_v2.py','assess_selected_isolated_control.py','queue_keeper_conditional_replay.py','retain_completed_native_trace.py']]]
    pins={str(q):sha(q) for q in files};output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{24});save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    save(output/'inputs.json',dict(input_sha256=pins,reference=str(reference),physical_assessment=str(physical),native_executable=str(binary),native_executable_sha256=backend_hash,BSIM_PBSWGD_default_corrected=False,old_backend_runtime_benchmark_only=True,current_type_variables_masked_from_LTE=True,voltage_LTE_control_retained=True,CPU=24,memory_GiB=8,queue_cap_s=172800,native_cap_s=14400,maximum_native_cases=1,automatic_identical_retry=False,PLLOUT_forcing_forbidden=True,release_ready=False));queue_deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+172800
    try:
        while True:
            state=json.loads((reference/'status.json').read_text())['state']
            if state=='flat_native_programming_transient_complete':break
            if state=='stopped_without_qualification':raise RuntimeError('full native reference stopped without completion')
            if identity(owner['pid'])!=owner['birth']:raise RuntimeError('reference controller is gone without completed receipt')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=queue_deadline:raise TimeoutError('reference observation deadline; no native job changed')
            save(output/'status.json',dict(state='waiting_for_completed_all_voltage_reference',reference_state=state,release_ready=False));time.sleep(10)
        reference_receipt=reference/'assessment.json';a=json.loads(reference_receipt.read_text());completed_reference(a);checked_backend(a,backend_hash);verify(a['input_sha256']);verify(a['artifacts']);verify(pins)
        while True:
            state=json.loads((physical/'status.json').read_text())['state']
            if state=='physical_tuning_voltage_assessment_complete':break
            if state=='stopped_without_qualification':raise RuntimeError('physical tuning validation stopped')
            po=json.loads((physical/'owner.json').read_text())
            if identity(po['pid'])!=po['birth']:raise RuntimeError('physical observer gone without receipt')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=queue_deadline:raise TimeoutError('physical observation deadline; no native job changed')
            save(output/'status.json',dict(state='waiting_for_completed_corrected_physical_controls',release_ready=False));time.sleep(10)
        physical_receipt=physical/'assessment.json';pr=json.loads(physical_receipt.read_text());verify(pr['input_sha256']);verify(pr['artifacts'])
        if pr['input_sha256'].get(str(reference_receipt))!=sha(reference_receipt) or not pr['all_macro_and_DCO_tuning_bits_match'] or pr['observed_bits']!=302 or pr['observed_endpoint_voltages']!=604 or (pr['coarse'],pr['fine'])!=(ri['coarse'],ri['fine']):raise ValueError('matching complete physical controls required')
        pins[str(physical_receipt)]=sha(physical_receipt)
        preparation_start=time.monotonic()
        while True:
            state=json.loads((staging/'status.json').read_text())['state']
            if state=='local_sources_and_verified_archive_complete' and (staging/'assessment.json').exists():break
            if state=='stopped_without_qualification':raise RuntimeError('local source staging stopped')
            so=json.loads((staging/'owner.json').read_text())
            if identity(so['pid'])!=so['birth']:raise RuntimeError('staging owner gone without completed receipt')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=queue_deadline:raise TimeoutError('source staging observation deadline')
            save(output/'status.json',dict(state='waiting_for_verified_local_shared_sources',release_ready=False));time.sleep(10)
        staging_receipt=staging/'assessment.json';stage=json.loads(staging_receipt.read_text());verify(stage['input_sha256']);verify(stage['artifacts'])
        if not stage['shared_knot_carrier_requested'] or not stage['all_source_archive_members_hash_verified']:raise ValueError('completed verified shared-knot archive required')
        source_root=Path(stage['local_sources']);source_receipt=source_root/'assessment.json';s=json.loads(source_receipt.read_text());verify(s['input_sha256']);verify(s['artifacts'])
        wr=waveforms/'assessment.json';w=json.loads(wr.read_text());verify(w['input_sha256']);verify(w['artifacts'])
        original_receipt=original_waveforms/'assessment.json';original=json.loads(original_receipt.read_text());verify(original['input_sha256']);verify(original['artifacts'])
        if not w.get('exact_sample_roundoff_audit_complete') or not w.get('all_original_time_knots_preserved') or w.get('native_simulation_allowed') is not False:raise ValueError('completed audited reduced samples required')
        if w['input_sha256'].get(str(reduction_receipt))!=sha(reduction_receipt) or w['input_sha256'].get(str(original_receipt))!=sha(original_receipt):raise ValueError('weighted samples use different reduction or original capture')
        if stage['input_sha256'].get(str(source_receipt))!=sha(source_receipt) or s['input_sha256'].get(str(wr))!=sha(wr) or original['input_sha256'].get(str(reference_receipt))!=sha(reference_receipt) or original['input_sha256'].get(str(plan/'assessment.json'))!=sha(plan/'assessment.json'):raise ValueError('local sources belong to a different completed capture or plan')
        if not s['individual_table_breakpoints_disabled'] or not s['all_original_time_knots_requested'] or s['downsampling_requested']:raise ValueError('exact shared-knot source representation required')
        pins.update({**stage['artifacts'],str(staging_receipt):sha(staging_receipt)})
        preparation_s=time.monotonic()-preparation_start
        if s['PLLOUT_forced'] or s['driven_ports']!=len(reduced_bindings['externally_driven_ports']):raise ValueError('complete unforced source set required')
        library='/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.tech/ngspice/sky130.lib.spice';model=reduction/'model.spice';source=source_root/'external_sources.spice';raw=output/'replay.raw';deck=output/'replay.spice';local=Path(tempfile.mkdtemp(prefix='openpll-reduced-native-'));native_raw=local/'replay.raw';native_log=local/'native.log';native_memory=local/'memory.log'
        if shutil.disk_usage(local).free<1024**3:raise ValueError('at least 1 GiB free local native output space required')
        save(output/'local_outputs.json',dict(local_directory=str(local),native_RAW=str(native_raw),native_log=str(native_log),native_memory=str(native_memory),release_ready=False))
        text,out=replay_deck(model.read_text(),reduced_bindings,model,source,library,native_raw)
        if text.splitlines().count('.tran 10p 260n 0 10p')!=1:raise ValueError('one replay transient command required')
        text=text.replace('.tran 10p 260n 0 10p','.tran 10p 260n 0 50p')
        if '.options timeint' in text.lower():raise ValueError('unexpected existing time integration options')
        text=text.replace('.tran 10p 260n 0 50p','.options timeint maskivars=1\n.tran 10p 260n 0 50p');deck.write_text(text)
        native_pins={**reduced['input_sha256'],**reduced['artifacts'],**w['artifacts'],**c['input_sha256'],**s['artifacts'],**pins,**{str(q):sha(q) for q in [reference_receipt,source_receipt,source,deck,binary,output/'local_outputs.json']}};verify(native_pins);save(output/'native_inputs.json',dict(input_sha256=native_pins,native_executable=str(binary),native_executable_sha256=backend_hash,BSIM_PBSWGD_default_corrected=False,old_backend_runtime_benchmark_only=True,current_type_variables_masked_from_LTE=True,voltage_LTE_control_retained=True,release_ready=False))
        deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+14400;save(output/'status.json',dict(state='conditional_native_replay_running',release_ready=False));start=time.monotonic()
        with lease(1,8,deadline):execute(['/usr/bin/time','-v','-o',native_memory,binary,'-a','-linsolv','umfpack_reuse',deck],native_log,deadline,8)
        elapsed=time.monotonic()-start;retentions=[retain(src,output/name,native_completed=True) for src,name in [(native_raw,'replay.raw'),(native_log,'native.log'),(native_memory,'memory.log')]];save(output/'native_output_retention.json',dict(files=retentions,all_completed_native_outputs_verified=True,release_ready=False));verify(native_pins);rows=read_selected(raw,{'output':out},260e-9);measured=frequency(rows,200,260);baseline=a['frequency_diagnostic']
        if baseline is None:raise ValueError('no completed full-reference frequency')
        delta=1e6*(measured['frequency_mhz']/baseline['frequency_mhz']-1)
        memory_rows=[line.split(':',1)[1].strip() for line in (output/'memory.log').read_text().splitlines() if 'Maximum resident set size (kbytes):' in line]
        if len(memory_rows)!=1 or not memory_rows[0].isdigit():raise ValueError('one native peak RSS measurement required')
        peak_rss_KiB=int(memory_rows[0])
        save(output/'assessment.json',dict(input_sha256=native_pins,artifacts={str(q):sha(q) for q in [deck,raw,output/'native.log',output/'memory.log',output/'local_outputs.json',output/'native_output_retention.json']},normal_native_replay_complete=True,local_native_output_staging_used=True,all_completed_native_outputs_copy_verified=True,native_executable=str(binary),native_executable_sha256=backend_hash,BSIM_PBSWGD_default_corrected=False,old_backend_runtime_benchmark_only=True,current_type_variables_masked_from_LTE=True,voltage_LTE_control_retained=True,all_physical_tuning_controls_correct=True,all_saved_replay_values_finite=True,native_peak_RSS_KiB=peak_rss_KiB,memory_limit_GiB=8,source_representation='FASTTABLEFILE with one shared PWL knot carrier',local_source_staging_used=True,shared_knot_carrier_used=True,source_generation_s=stage['source_generation_s'],source_archive_and_verification_s=stage['archive_and_verification_s'],literal_aggregated_samples_preserved=True,exact_original_boundary_samples_preserved=False,symbolic_boundary_reduction_used=True,roundoff_audited_at_source_samples=True,dynamic_aggregation_error_qualified=False,downsampling_requested=False,max_step_ps=50,numerical_timestep_accuracy_qualified=False,corrected_backend_memory_qualified=False,PLLOUT_forced=False,boundary_preparation_s=preparation_s,replay_native_elapsed_s=elapsed,full_reference_elapsed_s=a['elapsed_s'],output_capture_scope_differs=True,frequency_diagnostic=measured,full_reference_frequency=baseline,frequency_difference_ppm=delta,sampled_boundary_replay_only=True,independently_predictive_DCO_model=False,native_hierarchy_correlation_qualified=False,model_qualified=False,release_ready=False));save(output/'status.json',dict(state='conditional_native_replay_complete',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),release_ready=False));raise

if __name__=='__main__':
    q=argparse.ArgumentParser()
    for n in ['reference','conditional','plan','physical','original_waveforms','reduction','waveforms','staging','output']:q.add_argument('--'+n,type=Path,required=True)
    a=q.parse_args();run(*(getattr(a,n).resolve() for n in ['reference','conditional','plan','physical','original_waveforms','reduction','waveforms','staging','output']))
