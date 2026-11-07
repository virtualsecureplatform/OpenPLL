"""Wait for a predeclared fresh raw-corner holdout and replay frozen bytes once."""
import argparse,json,os,subprocess,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease


def prelaunch(protocol,owner,ticks):
    if protocol.get('role')!='fresh independent validation; excluded from all parameter selection':
        raise ValueError('explicit fresh independent validation role required')
    if int(owner['birth'])/ticks < protocol['created_boottime_s']:
        raise ValueError('validation protocol must predate native case launch')


def assess(protocol_path,output):
    from fit_selected_corner_detector import observe_corner
    from fit_selected_detector_diagnostic import replay
    if output.exists():raise FileExistsError(output)
    p=json.loads(protocol_path.read_text());verify(p['input_sha256'])
    case=Path(p['case']);owner=case/'owner.json'
    prelaunch(p,json.loads((case/'native/owner.json').read_text()),os.sysconf('SC_CLK_TCK'))
    if json.loads((case/'status.json').read_text()).get('state')!='corner_detector_response_measured':
        raise ValueError('normally completed native case required')
    paths=[Path(x) for x in p['input_sha256']]
    unique=lambda suffix: [x for x in paths if str(x).endswith(suffix)]
    params_paths=unique('/parameters.json');models=unique('/detector.v')
    if len(params_paths)!=1 or len(models)!=1 or params_paths[0].parent!=models[0].parent:
        raise ValueError('unique frozen parameter/model pair required')
    params_path=params_paths[0];model=models[0];params=json.loads(params_path.read_text())
    if params['operating_point']!={'corner':p['corner'],'temperature_c':27,'supply_v':1.8}:
        raise ValueError('frozen candidate and holdout corners must match')
    assessment=case/'waveform_assessment/assessment.json'
    previous=[x for x in paths if str(x).endswith('/assessment.json')]
    if not previous:raise ValueError('prelaunch candidate comparison receipt required')
    for receipt in previous:
        old=json.loads(receipt.read_text());verify(old['input_sha256']);verify(old.get('artifacts',{}))
        if any(r.get('assessment')==str(assessment) for r in old.get('records',[])):
            raise ValueError('fresh holdout already used in candidate comparison')
    o=observe_corner(assessment,p['corner'])
    manifest=case/'manifest.json';m=json.loads(manifest.read_text());verify(m['input_sha256'])
    if m['phase_ns']!=p['recorded_phase_ns'] or m['corner']!=p['corner']:
        raise ValueError('native case differs from predeclared phase/corner')
    helpers=['common_v3.py','resources.py','fit_selected_corner_detector.py','fit_selected_detector_diagnostic.py','selected_spice_device_conditions.py','audit_selected_dco_history_inputs.py']
    paths += [protocol_path,owner,assessment,manifest,Path(__file__).resolve(),Path('/usr/bin/iverilog'),Path('/usr/bin/vvp'),*o['binding_paths']]
    paths += [Path(__file__).with_name(n) for n in helpers]
    pins={str(x):sha(x) for x in paths};output.mkdir(parents=True)
    result=replay(o,params,model,output/'replay');verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(x):sha(x) for x in output.rglob('*') if x.is_file()},record=result,
        parameters_refitted=False,predeclared_fresh_independent_holdout=True,
        all_sampled_signs_match=result['all_sampled_signs_match'],all_event_counts_match=result['all_event_counts_match'],
        all_edges_within_observed_fit_band=result['all_edges_within_observed_fit_band'],
        corner_sender_waveforms_correlated=False,closed_loop_stress_executed=False,native_interface_qualified=False,release_ready=False))


def follow(protocol_path,output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{26})
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    try:
        p=json.loads(protocol_path.read_text());verify(p['input_sha256']);case=Path(p['case'])
        owner_path=case/'owner.json';owner=json.loads(owner_path.read_text());prelaunch(p,json.loads((case/'native/owner.json').read_text()),os.sysconf('SC_CLK_TCK'))
        image=ROOT/'build/apptainer/openpll-release-modern.sif'
        pins={str(x):sha(x) for x in [protocol_path,owner_path,case/'native/owner.json',Path(__file__).resolve(),image]}
        save(output/'inputs.json',dict(input_sha256=pins,case=str(case),native_cases_launched=0,automatic_identical_retry=False,release_ready=False))
        deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+14400
        while True:
            state=json.loads((case/'status.json').read_text())['state']
            if state=='corner_detector_response_measured':break
            if state=='stopped_without_qualification' or identity(owner['pid'])!=owner['birth']:
                raise ValueError('native case stopped without complete response')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('original native job unchanged')
            save(output/'status.json',dict(state='waiting_for_frozen_candidate_holdout',release_ready=False));time.sleep(10)
        verify(pins);save(output/'status.json',dict(state='replaying_frozen_candidate',release_ready=False))
        with lease(1,2,time.clock_gettime(time.CLOCK_BOOTTIME)+600), (output/'replay.log').open('x') as log:
            subprocess.run(['/usr/bin/apptainer','exec','--bind','/home:/home,/tmp:/tmp',str(image),'/usr/bin/python3',str(Path(__file__).resolve()),'--worker','--protocol',str(protocol_path),'--output',str(output/'check')],check=True,stdout=log,stderr=subprocess.STDOUT,timeout=600)
        verify(pins);receipt=output/'check/assessment.json';a=json.loads(receipt.read_text())
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(receipt):sha(receipt)},**{k:a[k] for k in ['all_sampled_signs_match','all_event_counts_match','all_edges_within_observed_fit_band']},parameters_refitted=False,native_interface_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='frozen_candidate_holdout_assessed',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),original_native_job_unchanged=True,release_ready=False));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--protocol',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--worker',action='store_true')
    a=p.parse_args();(assess if a.worker else follow)(a.protocol.resolve(),a.output.resolve())
