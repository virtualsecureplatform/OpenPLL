"""One bounded conditional replay after a complete full-reference waveform capture."""
import os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1')
import argparse,json,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease
from extract_keeper_replay_waveforms import run as extract_run,completed_reference
from write_keeper_replay_sources import run as sources_run
from compiled_charge_v2 import execute
from assess_selected_detector_phase_probe_v2 import read_selected
from assess_selected_isolated_control import frequency

def replay_deck(text,bindings,model,sources,library,raw):
    roots=[s.split() for s in text.splitlines() if s.startswith('.subckt ') and not s.split()[1].startswith('__openpll_')]
    if len(roots)!=1:raise ValueError('one conditional native root required')
    root=roots[0];ports=root[2:];observed=bindings['observation_only_ports'];driven=bindings['externally_driven_ports']
    if set(observed)!={'PLLOUT'} or 'PLLOUT' in driven:raise ValueError('unforced oscillator output required')
    if set(ports)!=set(driven.values())|set(observed.values()) or len(ports)!=len(driven)+1:raise ValueError('complete unique external source interface required')
    out=observed['PLLOUT']
    if out in driven.values():raise ValueError('output shares a driven port')
    deck='* Conditional sampled-boundary replay; not an independently predictive DCO model\n'+f'.lib "{library}" tt\n.include "{model}"\n.include "{sources}"\nXDUT '+' '.join(ports)+' '+root[1]+'\n.options parser model_binning=true\n.options device temp=27\n.options nonlin reltol=1e-5 abstol=1e-9\n.tran 10p 260n 0 10p\n.print tran format=raw precision=17 file='+str(raw)+' V('+out+')\n.end\n'
    return deck,out

def run(reference,conditional,plan,output):
    receipts=[p/'assessment.json' for p in [conditional,plan]];c,p=[json.loads(q.read_text()) for q in receipts]
    for r in [c,p]:verify(r['input_sha256']);verify(r['artifacts'])
    if p['input_sha256'].get(str(receipts[0]))!=sha(receipts[0]):raise ValueError('plan belongs to another conditional model')
    if not c['PLLOUT_not_externally_driven'] or not p['PLLOUT_forcing_forbidden']:raise ValueError('checked free-output preparations required')
    owner_file=reference/'owner.json';owner=json.loads(owner_file.read_text());folder=Path(__file__).resolve().parent
    files=[*receipts,owner_file,conditional/'model.spice',conditional/'bindings.json',plan/'ports.json',Path(__file__).resolve(),*[folder/n for n in ['extract_keeper_replay_waveforms.py','write_keeper_replay_sources.py','plan_keeper_conditional_replay.py','compiled_charge_v2.py','assess_selected_detector_phase_probe_v2.py','assess_selected_isolated_control.py']]]
    pins={str(q):sha(q) for q in files};output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{24});save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    save(output/'inputs.json',dict(input_sha256=pins,reference=str(reference),CPU=24,memory_GiB=64,queue_cap_s=172800,native_cap_s=86400,maximum_native_cases=1,automatic_identical_retry=False,PLLOUT_forcing_forbidden=True,release_ready=False));queue_deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+172800
    try:
        while True:
            state=json.loads((reference/'status.json').read_text())['state']
            if state=='flat_native_programming_transient_complete':break
            if state=='stopped_without_qualification':raise RuntimeError('full native reference stopped without completion')
            if identity(owner['pid'])!=owner['birth']:raise RuntimeError('reference controller is gone without completed receipt')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=queue_deadline:raise TimeoutError('reference observation deadline; no native job changed')
            save(output/'status.json',dict(state='waiting_for_completed_all_voltage_reference',reference_state=state,release_ready=False));time.sleep(10)
        reference_receipt=reference/'assessment.json';a=json.loads(reference_receipt.read_text());completed_reference(a);verify(pins)
        preparation_start=time.monotonic();save(output/'status.json',dict(state='extracting_completed_boundary_waveforms',release_ready=False))
        with lease(1,8,time.clock_gettime(time.CLOCK_BOOTTIME)+7200):
            extract_run(reference,plan,output/'waveforms');sources_run(output/'waveforms',output/'sources')
        preparation_s=time.monotonic()-preparation_start
        source_receipt=output/'sources/assessment.json';s=json.loads(source_receipt.read_text());verify(s['input_sha256']);verify(s['artifacts'])
        if s['PLLOUT_forced'] or s['driven_ports']!=c['externally_driven_port_count']:raise ValueError('complete unforced source set required')
        library='/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.tech/ngspice/sky130.lib.spice';model=conditional/'model.spice';source=output/'sources/external_sources.spice';raw=output/'replay.raw';deck=output/'replay.spice'
        text,out=replay_deck(model.read_text(),json.loads((conditional/'bindings.json').read_text()),model,source,library,raw);deck.write_text(text);binary=ROOT/'build/tools/xyce_umfpack_value_gather_001/Xyce'
        native_pins={**c['input_sha256'],**pins,**{str(q):sha(q) for q in [reference_receipt,source_receipt,source,deck,binary]}};verify(native_pins);save(output/'native_inputs.json',dict(input_sha256=native_pins,release_ready=False))
        deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+86400;save(output/'status.json',dict(state='conditional_native_replay_running',release_ready=False));start=time.monotonic()
        with lease(1,64,deadline):execute([binary,'-a','-linsolv','umfpack_reuse',deck],output/'native.log',deadline,64)
        elapsed=time.monotonic()-start;verify(native_pins);rows=read_selected(raw,{'output':out},260e-9);measured=frequency(rows,200,260);baseline=a['frequency_diagnostic']
        if baseline is None:raise ValueError('no completed full-reference frequency')
        delta=1e6*(measured['frequency_mhz']/baseline['frequency_mhz']-1)
        save(output/'assessment.json',dict(input_sha256=native_pins,artifacts={str(q):sha(q) for q in [deck,raw,output/'native.log']},normal_native_replay_complete=True,all_saved_replay_values_finite=True,PLLOUT_forced=False,boundary_preparation_s=preparation_s,replay_native_elapsed_s=elapsed,full_reference_elapsed_s=a['elapsed_s'],output_capture_scope_differs=True,frequency_diagnostic=measured,full_reference_frequency=baseline,frequency_difference_ppm=delta,sampled_boundary_replay_only=True,independently_predictive_DCO_model=False,native_hierarchy_correlation_qualified=False,model_qualified=False,release_ready=False));save(output/'status.json',dict(state='conditional_native_replay_complete',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),release_ready=False));raise

if __name__=='__main__':
    q=argparse.ArgumentParser()
    for n in ['reference','conditional','plan','output']:q.add_argument('--'+n,type=Path,required=True)
    a=q.parse_args();run(*(getattr(a,n).resolve() for n in ['reference','conditional','plan','output']))
