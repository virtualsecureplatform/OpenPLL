"""Bounded 8 GiB old-backend replay benchmark from a completed 50 ps capture."""
import os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',LC_ALL='C')
import argparse,json,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease
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


def run(reference,conditional,plan,physical,waveforms,output):
    receipts=[p/'assessment.json' for p in [conditional,plan]];c,p=[json.loads(q.read_text()) for q in receipts]
    for r in [c,p]:verify(r['input_sha256']);verify(r['artifacts'])
    if p['input_sha256'].get(str(receipts[0]))!=sha(receipts[0]):raise ValueError('plan belongs to another conditional model')
    if not c['PLLOUT_not_externally_driven'] or not p['PLLOUT_forcing_forbidden']:raise ValueError('checked free-output preparations required')
    binary=ROOT/'build/tools/xyce_umfpack_value_gather_001/Xyce';backend_hash=sha(binary);reference_inputs=reference/'inputs.json';ri=json.loads(reference_inputs.read_text());checked_backend(ri,backend_hash);verify(ri['input_sha256'])
    physical_plan=physical/'plan.json';pp=json.loads(physical_plan.read_text());verify(pp['input_sha256'])
    if pp['input_sha256'].get(str(reference_inputs))!=sha(reference_inputs) or (ri['corner'],ri['temperature_C'],ri['supply_V'],ri['max_step_ps'],ri['simulation_ns'])!=('tt',27,1.8,50,260) or not ri['all_node_voltages_requested']:raise ValueError('matching physical plan and full 50 ps TT capture required')
    controls=ROOT/'build/signoff400/selected_xyce_TABLEFILE_boundary_controls_1368/assessment.json';cr=json.loads(controls.read_text());verify(cr['input_sha256']);verify(cr['artifacts'])
    if not cr['all_twelve_native_controls_complete'] or not cr['literal_source_samples_and_knot_breakpoints_verified']:raise ValueError('complete native TABLEFILE controls required')
    owner_file=reference/'owner.json';owner=json.loads(owner_file.read_text());folder=Path(__file__).resolve().parent
    files=[controls,waveforms/'assessment.json',Path('/usr/bin/time'),*receipts,owner_file,reference_inputs,binary,physical/'owner.json',physical/'plan.json',conditional/'model.spice',conditional/'bindings.json',plan/'ports.json',Path(__file__).resolve(),*[folder/n for n in ['extract_keeper_replay_waveforms.py','write_keeper_tablefile_sources.py','plan_keeper_conditional_replay.py','compiled_charge_v2.py','assess_selected_detector_phase_probe_v2.py','assess_selected_isolated_control.py','queue_keeper_conditional_replay.py']]]
    pins={str(q):sha(q) for q in files};output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{29});save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    save(output/'inputs.json',dict(input_sha256=pins,reference=str(reference),physical_assessment=str(physical),native_executable=str(binary),native_executable_sha256=backend_hash,BSIM_PBSWGD_default_corrected=False,old_backend_runtime_benchmark_only=True,CPU=29,memory_GiB=8,queue_cap_s=172800,native_cap_s=1800,maximum_native_cases=1,automatic_identical_retry=False,PLLOUT_forcing_forbidden=True,release_ready=False));queue_deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+172800
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
        preparation_start=time.monotonic();save(output/'status.json',dict(state='extracting_completed_boundary_waveforms',release_ready=False))
        with lease(1,8,time.clock_gettime(time.CLOCK_BOOTTIME)+7200):
            wr=waveforms/'assessment.json';w=json.loads(wr.read_text());verify(w['input_sha256']);verify(w['artifacts'])
            if w['input_sha256'].get(str(reference_receipt))!=sha(reference_receipt) or w['input_sha256'].get(str(plan/'assessment.json'))!=sha(plan/'assessment.json'):raise ValueError('completed waveforms belong to a different capture or plan')
            sources_run(waveforms,output/'sources')
        preparation_s=time.monotonic()-preparation_start
        source_receipt=output/'sources/assessment.json';s=json.loads(source_receipt.read_text());verify(s['input_sha256']);verify(s['artifacts'])
        if s['PLLOUT_forced'] or s['driven_ports']!=c['externally_driven_port_count']:raise ValueError('complete unforced source set required')
        library='/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.tech/ngspice/sky130.lib.spice';model=conditional/'model.spice';source=output/'sources/external_sources.spice';raw=output/'replay.raw';deck=output/'replay.spice'
        text,out=replay_deck(model.read_text(),json.loads((conditional/'bindings.json').read_text()),model,source,library,raw)
        if text.splitlines().count('.tran 10p 260n 0 10p')!=1:raise ValueError('one replay transient command required')
        text=text.replace('.tran 10p 260n 0 10p','.tran 10p 260n 0 50p');deck.write_text(text)
        native_pins={**c['input_sha256'],**s['artifacts'],**pins,**{str(q):sha(q) for q in [reference_receipt,source_receipt,source,deck,binary]}};verify(native_pins);save(output/'native_inputs.json',dict(input_sha256=native_pins,native_executable=str(binary),native_executable_sha256=backend_hash,BSIM_PBSWGD_default_corrected=False,old_backend_runtime_benchmark_only=True,release_ready=False))
        deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1800;save(output/'status.json',dict(state='conditional_native_replay_running',release_ready=False));start=time.monotonic()
        with lease(1,8,deadline):execute(['/usr/bin/time','-v','-o',output/'memory.log',binary,'-a','-linsolv','umfpack_reuse',deck],output/'native.log',deadline,8)
        elapsed=time.monotonic()-start;verify(native_pins);rows=read_selected(raw,{'output':out},260e-9);measured=frequency(rows,200,260);baseline=a['frequency_diagnostic']
        if baseline is None:raise ValueError('no completed full-reference frequency')
        delta=1e6*(measured['frequency_mhz']/baseline['frequency_mhz']-1)
        memory_rows=[line.split(':',1)[1].strip() for line in (output/'memory.log').read_text().splitlines() if 'Maximum resident set size (kbytes):' in line]
        if len(memory_rows)!=1 or not memory_rows[0].isdigit():raise ValueError('one native peak RSS measurement required')
        peak_rss_KiB=int(memory_rows[0])
        save(output/'assessment.json',dict(input_sha256=native_pins,artifacts={str(q):sha(q) for q in [deck,raw,output/'native.log',output/'memory.log']},normal_native_replay_complete=True,native_executable=str(binary),native_executable_sha256=backend_hash,BSIM_PBSWGD_default_corrected=False,old_backend_runtime_benchmark_only=True,all_physical_tuning_controls_correct=True,all_saved_replay_values_finite=True,native_peak_RSS_KiB=peak_rss_KiB,memory_limit_GiB=8,source_representation='linear TABLEFILE with native knot breakpoints',literal_samples_preserved=True,downsampling_requested=False,max_step_ps=50,numerical_timestep_accuracy_qualified=False,corrected_backend_memory_qualified=False,PLLOUT_forced=False,boundary_preparation_s=preparation_s,replay_native_elapsed_s=elapsed,full_reference_elapsed_s=a['elapsed_s'],output_capture_scope_differs=True,frequency_diagnostic=measured,full_reference_frequency=baseline,frequency_difference_ppm=delta,sampled_boundary_replay_only=True,independently_predictive_DCO_model=False,native_hierarchy_correlation_qualified=False,model_qualified=False,release_ready=False));save(output/'status.json',dict(state='conditional_native_replay_complete',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),release_ready=False));raise

if __name__=='__main__':
    q=argparse.ArgumentParser()
    for n in ['reference','conditional','plan','physical','waveforms','output']:q.add_argument('--'+n,type=Path,required=True)
    a=q.parse_args();run(*(getattr(a,n).resolve() for n in ['reference','conditional','plan','physical','waveforms','output']))
