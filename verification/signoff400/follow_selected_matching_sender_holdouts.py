"""Consume existing corner packets with bounded, predeclared frozen-model holdouts."""
import argparse,json,math,os,subprocess,sys,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease

CORNERS=['ff','ss','sf','fs']
PHASES=[-1.,1.]


def validate_schedule(fits,phases):
    if set(fits)!=set(CORNERS):raise ValueError('exactly four non-TT fit bindings required')
    if len(phases)!=2 or any(not math.isfinite(x)or not -7<=x<=30 for x in phases)or not phases[0]<0<phases[1]:raise ValueError('distinct finite opposite recorded phases required')
    return [dict(corner=c,fit=str(fits[c]),phase_ns=p)for c in CORNERS for p in phases]


def preflight(protocol,output):
    from check_selected_matching_sender_holdout import fit_corner
    if output.exists():raise FileExistsError(output)
    a=json.loads(protocol.read_text());verify(a['input_sha256']);records=[];model=None;files=[protocol,Path(__file__).resolve()]
    for corner,folder in a['fits'].items():
        fit=Path(folder);receipt=fit/'assessment.json';r=json.loads(receipt.read_text());verify(r['input_sha256']);verify(r['artifacts'])
        if fit_corner(r)!=corner:raise ValueError('frozen fit corner differs from schedule')
        for name in ['parameters.json','detector.v']:
            p=fit/name
            if r['artifacts'].get(str(p))!=sha(p):raise ValueError('fit receipt must bind unchanged parameters/model')
            files.append(p)
        parameters=json.loads((fit/'parameters.json').read_text())
        if parameters.get('operating_point')!={'corner':corner,'temperature_c':27,'supply_v':1.8}:raise ValueError('parameters must match the scheduled fit corner')
        verify(r['native_model_sha256'])
        if model is None:model=r['native_model_sha256']
        if r['native_model_sha256']!=model:raise ValueError('same physical native model required across fits')
        records.append(dict(corner=corner,fit=str(fit),parameters_refitted=False));files.append(receipt)
    save(output,dict(input_sha256={str(p):sha(p)for p in files},fits=records,native_model_sha256=model,all_four_frozen_fit_bindings_verified=True,release_ready=False))


def wait_packet(packets,owner,corner,deadline,status):
    while True:
        path=packets/'completed_packets.json';available=[]
        if path.exists():
            try:available=json.loads(path.read_text())
            except json.JSONDecodeError:pass # A concurrent non-atomic publication is an observation retry.
        matches=[r for r in available if r['corner']==corner]
        if len(matches)>1:raise ValueError('duplicate corner packet')
        if matches:return matches[0]
        if identity(owner['pid'])!=owner['birth']:raise RuntimeError('packet owner exited before usable '+corner+' packet')
        state=json.loads((packets/'status.json').read_text()).get('state')
        if state=='stopped_without_qualification':raise RuntimeError('original packet capture stopped before '+corner)
        if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('packet observation deadline; original jobs unchanged')
        save(status,dict(state='waiting_for_matching_corner_sender_packet',corner=corner,release_ready=False));time.sleep(10)


def run(packets,fits,output):
    if output.exists():raise FileExistsError(output)
    schedule=validate_schedule(fits,PHASES);output.mkdir(parents=True);os.sched_setaffinity(0,{28})
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    folder=Path(__file__).resolve().parent;image=ROOT/'build/apptainer/openpll-release-modern.sif';binary=ROOT/'build/tools/xyce_umfpack_value_gather_001/Xyce';ownerpath=packets/'owner.json';owner=json.loads(ownerpath.read_text())
    helpers=['common_v3.py','resources.py','run_selected_corner_detector_case_v3.py','run_selected_detector_phase_probe_v12.py','assess_selected_detector_phase_probe_v4.py','characterize_selected_detector_response_v3.py','check_selected_matching_sender_holdout.py','selected_matching_corner_sender.py','selected_detector_level_observations.py','fit_selected_detector_diagnostic.py','capture_selected_native_runtime.py']
    files=[Path(__file__).resolve(),image,binary,ownerpath,*[folder/n for n in helpers]]
    files += [fit/name for fit in fits.values()for name in ['assessment.json','parameters.json','detector.v']]
    pins={str(p):sha(p)for p in files};verify(pins);protocol=output/'protocol.json'
    save(protocol,dict(input_sha256=pins,packet_source=str(packets),packet_source_owner=owner,fits={c:str(fits[c])for c in CORNERS},schedule=schedule,phases_chosen_before_packet_observation=True,CPU=24,memory_GiB=12,native_cap_s=10800,maximum_native_cases=8,maximum_full_native_cases=0,automatic_identical_retry=False,parameters_refitted=False,FF_prior_nominal_already_rejected=True,scope='sender transfer at two sampled phases only; not nominal-fit repair or full-phase qualification',release_ready=False))
    prefix=['apptainer','exec','--bind','/home:/home,/tmp:/tmp,'+str(ROOT)+':/work/OpenPLL',str(image),'python3']
    records=[];deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+12*86400
    try:
        save(output/'status.json',dict(state='preflighting_frozen_corner_fits',release_ready=False))
        with (output/'preflight.log').open('x')as log:
            subprocess.run(prefix+[str(Path(__file__).resolve()),'--preflight',str(protocol),'--output',str(output/'preflight.json')],check=True,stdout=log,stderr=subprocess.STDOUT,timeout=600)
        for corner in CORNERS:
            record=wait_packet(packets,owner,corner,deadline,output/'status.json');verify(record['artifacts']);verify(pins)
            from selected_matching_corner_sender import validate
            native=Path(record['source_native']);packet=packets/corner
            op,bindings=validate(native,packet/'snapshot',packet/'waveforms',corner)
            if op!=record['operating_point']:raise ValueError('published packet operating point changed')
            target=output/corner;target.mkdir();assessments=[];case_records=[]
            save(target/'prelaunch.json',dict(input_sha256={**pins,**bindings},corner=corner,source_native=str(native),operating_point=op,phases_ns=PHASES,parameters_refitted=False,release_ready=False))
            for index,phase in enumerate(PHASES):
                case=target/('negative'if phase<0 else'positive');logpath=target/('case%d.log'%index)
                command=[sys.executable,str(folder/'run_selected_corner_detector_case_v3.py'),'--phase-ns',str(phase),'--cpu','24','--output',str(case),'--corner',corner,'--initial-snapshot',str(packet/'snapshot'),'--native',str(native),'--clock-waveforms',str(packet/'waveforms')]
                save(output/'status.json',dict(state='matching_corner_receiver_holdout_running',corner=corner,phase_ns=phase,release_ready=False))
                with logpath.open('x')as log:
                    process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT);start=time.monotonic();captured=False
                    while process.poll()is None:
                        no=case/'native/owner.json'
                        if not captured and no.exists():
                            try:o=json.loads(no.read_text())
                            except json.JSONDecodeError:o=None
                            if o and identity(o['pid'])==o['birth']:
                                from capture_selected_native_runtime import capture
                                lib='/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.tech/ngspice/sky130.lib.spice'
                                with lease(1,2,time.clock_gettime(time.CLOCK_BOOTTIME)+600):capture(case/'native',lib,image,case/'runtime.json')
                                captured=True
                        if time.monotonic()-start>15000:
                            process.terminate();process.wait(timeout=30);raise TimeoutError('bounded receiver wrapper deadline; no identical retry')
                        time.sleep(2)
                    if process.returncode!=0:raise RuntimeError('receiver case stopped: '+str(case))
                if not captured:raise ValueError('live PDK capture missing; no qualification claimed')
                assessment=case/'waveform_assessment/assessment.json'
                if json.loads((case/'status.json').read_text()).get('state')!='corner_detector_response_measured':raise ValueError('normal complete receiver case required')
                assessments.append(assessment);case_records.append(dict(case=str(case),phase_ns=phase,runtime=str(case/'runtime.json'),normal_completion=True))
                verify(pins)
            destination=target/'frozen_replay';command=prefix+[str(folder/'check_selected_matching_sender_holdout.py'),'--fit',str(fits[corner]),'--output',str(destination)]
            for a in assessments:command += ['--assessment',str(a)]
            with lease(1,4,time.clock_gettime(time.CLOCK_BOOTTIME)+1200),(target/'replay.log').open('x')as log:subprocess.run(command,check=True,stdout=log,stderr=subprocess.STDOUT,timeout=1200)
            receipt=destination/'assessment.json';result=json.loads(receipt.read_text());verify(pins)
            records.append(dict(corner=corner,assessment=str(receipt),sha256=sha(receipt),cases=case_records,**{k:result[k]for k in ['all_sampled_signs_match','all_event_counts_match','all_edges_within_observed_fit_band']},nominal_fit_qualified=False))
            save(output/'completed_corners.json',records)
        save(output/'assessment.json',dict(input_sha256=pins,corners=records,parameters_refitted=False,corner_sender_waveforms_correlated=True,conditional_reset_and_exterior_qualified=False,full_phase_coverage_qualified=False,FF_prior_nominal_failure_resolved=False,native_interface_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='four_matching_sender_holdouts_assessed',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),original_native_jobs_unchanged=True,release_ready=False));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--preflight',type=Path);p.add_argument('--packets',type=Path);p.add_argument('--output',type=Path,required=True)
    for corner in CORNERS:p.add_argument('--'+corner+'-fit',type=Path)
    a=p.parse_args()
    if a.preflight:preflight(a.preflight.resolve(),a.output.resolve())
    else:
        if not a.packets or any(getattr(a,c+'_fit')is None for c in CORNERS):p.error('packet source and all four fits required')
        run(a.packets.resolve(),{c:getattr(a,c+'_fit').resolve()for c in CORNERS},a.output.resolve())
