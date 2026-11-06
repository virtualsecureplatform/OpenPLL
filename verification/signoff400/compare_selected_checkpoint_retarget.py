"""Compare a cross-code checkpoint challenge to independent target-code references."""
import argparse,csv,json,os,time
from pathlib import Path
from common_v3 import save,sha,verify
from resources import identity,lease
from assess_selected_detector_prefix import read_prefix
from compare_selected_dco_startup_aligned_v5 import aligned,metrics
from selected_spice_device_conditions import matching,reference_deck


def run(native,target,provenance_path,output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{24})
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    try:
        owner=json.loads((native/'owner.json').read_text());deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+11100
        while True:
            state=json.loads((native/'status.json').read_text())['state']
            if state not in('preparing_checkpoint_retarget','checkpoint_retarget_native_running'):break
            if identity(owner['pid'])!=owner['birth']:raise ValueError('original controller disappeared before completion')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('observer deadline; bounded native unchanged')
            save(output/'status.json',dict(state='waiting_for_retarget_challenge',release_ready=False));time.sleep(10)
        if state!='checkpoint_retarget_diagnostic_complete':raise ValueError('normally completed retarget challenge required')
        worker=json.loads((native/'native.process.json').read_text())
        if identity(worker['pid'])==worker['birth']:raise ValueError('original native worker still live')
        m=json.loads((native/'manifest.json').read_text());tm=json.loads((target/'manifest.json').read_text())
        for item in(m,tm):verify(item['input_sha256'])
        if m['checkpoint_fine']!=111 or m['coarse']!=20 or tm['controls']['coarse']!=20 or tm['controls']['fine']!=m['requested_fine']:raise ValueError('independently measured target code must differ from actual checkpoint code')
        if m['operating_point']!=tm['operating_point']or m['operating_point']!={'corner':'tt','temperature_c':27,'supply_v':1.8}:raise ValueError('same nominal TT device point required')
        if json.loads((target/'status.json').read_text())['state']!='saved_state_DCO_diagnostic_complete':raise ValueError('completed independent target-code checkpoint required')
        for directory in(native,target):
            assessment=json.loads((directory/'assessment.json').read_text());verify(assessment['input_sha256']);verify(assessment['artifacts'])
        devices=[{h for p,h in item['input_sha256'].items()if p.endswith('/devices.spice')}for item in(m,tm)]
        if any(len(x)!=1 for x in devices)or devices[0]!=devices[1]:raise ValueError('identical physical circuit cards required')
        provenance=json.loads(provenance_path.read_text());verify(provenance['input_sha256']);verify(provenance['artifacts'])
        reference=provenance_path.parent/'signals.csv';assessment_path=provenance_path.parent/'assessment.json';a=json.loads(assessment_path.read_text())
        for p in(reference,assessment_path):
            if provenance['artifacts'].get(str(p))!=sha(p):raise ValueError('full-native reference artifact identity differs')
        if a['end_ns']!=260 or a['coarse_code']['window_codes']!=[20]or a['dco_code']['window_codes']!=[m['requested_fine']]:raise ValueError('complete full-native target code required')
        models={p:h for p,h in m['input_sha256'].items()if p.endswith('/model.spice')}
        if len(models)!=1 or any(provenance['native_input_sha256'].get(p)!=h for p,h in models.items()):raise ValueError('full-native physical model differs')
        physical=reference_deck(provenance);matching(native/'control.spice',physical);matching(target/'control.spice',physical)
        with lease(1,2,deadline):
            c,ci=read_prefix(native/'control.raw',m['observed_roles']);t,ti=read_prefix(target/'control.raw',tm['observed_roles'])
            with reference.open()as stream:
                reader=csv.reader(stream);names=next(reader);full=[[float(v)for v in row]for row in reader]
        if len(full)!=a['samples']:raise ValueError('complete assessed full-native samples required')
        for rows,info,manifest in((c,ci,m),(t,ti,tm)):
            if info['incomplete_final_sample_discarded']or abs(rows[-1][0]-manifest['simulation_end_s'])>1e-18:raise ValueError('complete restart horizons required')
        ce,cm=aligned(c,1,2);te,ts=aligned(t,1,2);fe,fs=aligned(full,names.index('v(pllout)'),names.index('v(xpll:__parent_r_node_617)'))
        if min(cm['end_age_ns'],ts['end_age_ns'],fs['end_age_ns'])<40:raise ValueError('complete 10--40 ns common oscillator-age window required')
        paths=[provenance_path,reference,assessment_path,physical,Path(__file__).resolve(),*(Path(__file__).with_name(n)for n in('common_v3.py','resources.py','assess_selected_detector_prefix.py','compare_selected_dco_startup_aligned_v5.py','selected_spice_device_conditions.py'))]
        paths += [d/n for d in(native,target)for n in('manifest.json','assessment.json','status.json','control.raw','control.spice')]
        pins={str(p):sha(p)for p in paths};verify(pins)
        save(output/'assessment.json',dict(input_sha256=pins,normal_native_completions=True,checkpoint_fine=111,target_fine=m['requested_fine'],coarse=20,
            against_full_native=metrics(ce,fe,40),against_target_own_checkpoint=metrics(ce,te,40),candidate_startup=cm,target_checkpoint_startup=ts,full_native_startup=fs,
            scope='Cross-code saved-state challenge. Same physical cut; original fine111 voltages and reset history, new physical programming ramps under reset. Full-native and target-own-state references are independent. No target-state substitution.',
            cross_code_restart_qualified=False,uniform_model_uncertainty_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='retarget_response_assessed',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),original_native_unchanged=True,release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in('native','target','provenance','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve()for n in('native','target','provenance','output')))
