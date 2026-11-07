"""Test four external-pin standard-cell keepers against the same paired DCO IC states."""
import argparse,json,os,resource,signal,subprocess,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease
from selected_history_external_keepers import keeper_cards
from capture_selected_native_runtime import capture
from run_selected_checkpoint_IC_swap import initial
from assess_selected_detector_prefix import read_prefix
from assess_selected_isolated_control import frequency



def native(binary,deck,folder,image,deadline):
    def limits():resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
    child=None
    try:
        with (folder/'native.log').open('x')as log:
            child=subprocess.Popen([str(binary),'-a','-linsolv','umfpack_reuse',str(deck)],stdout=log,stderr=subprocess.STDOUT,start_new_session=True,preexec_fn=limits)
            owner=dict(pid=child.pid,birth=identity(child.pid),process_group=child.pid);save(folder/'owner.json',owner)
            # Observe the actual live Xyce namespace, not the outer controller.
            library='/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.tech/ngspice/sky130.lib.spice'
            capture(folder,library,image,folder/'runtime.json')
            remaining=deadline-time.clock_gettime(time.CLOCK_BOOTTIME)
            if remaining<=0:raise TimeoutError('native whole-case deadline exhausted')
            code=child.wait(timeout=remaining)
            if code!=0:raise RuntimeError('native clamp IC case stopped with code '+str(code))
    finally:
        if child is not None and child.poll()is None:
            os.killpg(child.pid,signal.SIGTERM)
            try:child.wait(timeout=3)
            except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()


def run(mapping,target,context,binary,image,output,keeper_template):
    if output.exists():raise FileExistsError(output)
    os.sched_setaffinity(0,{22});output.mkdir(parents=True);save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    mapped=json.loads(mapping.read_text());verify(mapped['input_sha256'])
    if not mapped['all_24_MOS_cards_and_wrappers_identical_in_measured_partition']or not mapped['all_four_Z_have_no_outside_primitives_or_resistors']:raise ValueError('verified physical history-cell mapping required')
    tm=target/'manifest.json';t=json.loads(tm.read_text());verify(t['input_sha256']);cm=context/'manifest.json';c=json.loads(cm.read_text());verify(c['input_sha256'])
    if t['controls']['coarse']!=20 or t['controls']['fine']!=112 or t['operating_point']!={'corner':'tt','supply_v':1.8,'temperature_c':27}:raise ValueError('same nominal TT20/fine112 partition required')
    own=target/'initial_conditions.spice';hybrid=context/'initial_conditions.spice';devices=target/'devices.spice';original=target/'control.spice'
    for p in [own,hybrid,devices]:
        if mapped['input_sha256'].get(str(p))!=sha(p):raise ValueError('same measured ICs and device include required')
    before,after=initial(own),initial(hybrid);nodes=set(mapped['context_node_locations'])
    if set(before)!=set(after)or any(before[n]!=after[n]for n in before if n not in nodes):raise ValueError('only the measured context may differ between ICs')
    text=devices.read_text();extra,added=keeper_cards(text,mapped['cells'],keeper_template);newdevices=output/'devices.spice';newdevices.write_text(text+(''if text.endswith('\n')else'\n')+extra)
    if not newdevices.read_bytes().startswith(devices.read_bytes()):raise ValueError('all original device/R/C bytes must be retained')
    files=[keeper_template/'assessment.json',keeper_template/'cut.spice',Path(__file__).with_name('selected_history_external_keepers.py'),mapping,tm,cm,own,hybrid,devices,original,target/'sources.spice',newdevices,binary,image,Path(__file__).resolve()]
    files += [Path(__file__).with_name(n)for n in ['common_v3.py','resources.py','capture_selected_native_runtime.py','run_selected_checkpoint_IC_swap.py','assess_selected_detector_prefix.py','assess_selected_isolated_control.py']]
    plans=[]
    for name,ic in [('own112',own),('context111',hybrid)]:
        folder=output/name;folder.mkdir();deck=folder/'control.spice';body=original.read_text()
        for old,new in [(devices,newdevices),(own,ic),(target/'control.raw',folder/'control.raw')]:
            if body.count(str(old))!=1:raise ValueError('unique device/IC/output substitution required')
            body=body.replace(str(old),str(new))
        deck.write_text(body);files.append(deck);plans.append(dict(name=name,initial_conditions=str(ic),deck=str(deck),output=str(folder)))
    pins=dict(t['input_sha256']);pins.update(c['input_sha256']);pins.update({str(p):sha(p)for p in files});verify(pins)
    protocol=output/'protocol.json';save(protocol,dict(input_sha256=pins,plans=plans,added_MOS=added,original_device_RC_bytes_retained=True,boundary_histories_reset_solver_and_horizon_unchanged=True,only_initial_context_differs_between_paired_cases=True,CPU=22,native_address_space_limit_GiB=8,aggregate_lease_GiB=10,native_cap_s=10800,maximum_serial_native_cases=2,new_full_native_cases=0,automatic_identical_retry=False,internal_original_enable_complement_tapped=False,added_standard_cells=dict(sky130_fd_sc_hd__einvp_1=4,sky130_fd_sc_hs__inv_2=4),new_cell_extracted_parasitics_included=False,physical_layout_changed=False,hybrid_physical_reachability_assumed=False,release_ready=False))
    results={}
    try:
        for plan in plans:
            verify(pins);folder=Path(plan['output']);save(output/'status.json',dict(state='external_keeper_checkpoint_native_running',case=plan['name'],release_ready=False));deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+10800
            start=time.monotonic()
            with lease(1,10,deadline):native(binary,Path(plan['deck']),folder,image,deadline)
            verify(pins);raw=folder/'control.raw';rows,info=read_prefix(raw,t['observed_roles'])
            if info['incomplete_final_sample_discarded']or abs(rows[-1][0]-t['simulation_end_s'])>1e-18:raise ValueError('complete common native horizon required')
            windows=[dict(window_ns=[lo,hi],frequency=frequency(rows,lo,hi))for lo,hi in [(35,45),(40,55),(50,59),(70,84)]]
            assessment=folder/'assessment.json';save(assessment,dict(input_sha256=pins,artifacts={str(raw):sha(raw),str(folder/'runtime.json'):sha(folder/'runtime.json'),str(folder/'native.log'):sha(folder/'native.log')},normal_native_completion=True,elapsed_seconds=time.monotonic()-start,windows=windows,release_ready=False));results[plan['name']]=dict(assessment=str(assessment),sha256=sha(assessment),windows=windows)
            save(output/'completed_cases.json',results)
        comparisons=[]
        for left,right,baseline in zip(results['own112']['windows'],results['context111']['windows'],mapped['factorial_windows']):
            if left['window_ns']!=right['window_ns']or left['window_ns']!=baseline['window_ns']:raise ValueError('identical measured windows required')
            own_frequency=left['frequency']['frequency_mhz'];other_frequency=right['frequency']['frequency_mhz'];delta=other_frequency-own_frequency;old=baseline['context_effect_with_other_state112_MHz']
            comparisons.append(dict(window_ns=left['window_ns'],clamped_own112_MHz=own_frequency,clamped_context111_MHz=other_frequency,clamped_context_effect_MHz=delta,unclamped_context_effect_MHz=old,absolute_residual_ratio=abs(delta/old),difference_ppm=(other_frequency/own_frequency-1)*1e6))
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(protocol):sha(protocol),**{r['assessment']:r['sha256']for r in results.values()}},both_native_cases_completed_normally=True,comparisons=comparisons,scope='Four external-pin standard-cell keepers in the same conditional TT112 DCO; two initial states only. Changed tuning, other states/codes/corners, full-native reachability and new layout remain unqualified.',physical_layout_changed=False,global_history_independence_qualified=False,full_native_switched_equivalence_qualified=False,model_family_qualified=False,release_ready=False));save(output/'status.json',dict(state='external_keeper_checkpoint_IC_pair_assessed',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),original_native_jobs_unchanged=True,release_ready=False));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['mapping','target','context','binary','image','output','keeper-template']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(a.mapping.resolve(),a.target.resolve(),a.context.resolve(),a.binary.resolve(),a.image.resolve(),a.output.resolve(),a.keeper_template.resolve())
