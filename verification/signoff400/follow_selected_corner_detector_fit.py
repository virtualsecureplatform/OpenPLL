"""Wait for one corner probe, then fit frozen observations with independent holdouts."""
import argparse,json,os,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease
from compiled_charge_v2 import execute


def run(case,fitting,holdouts,corner,output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{26});save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    try:
        folder=Path(__file__).resolve().parent;worker=folder/'fit_selected_corner_detector.py';image=ROOT/'build/apptainer/openpll-release-modern.sif';owner=json.loads((case/'owner.json').read_text())
        paths=[Path(__file__).resolve(),worker,image,case/'owner.json',case/'manifest.json',folder/'common_v3.py',folder/'resources.py',folder/'compiled_charge_v2.py',folder/'fit_selected_detector_diagnostic.py',folder/'fit_prototype_detector_model.py',folder/'selected_spice_device_conditions.py',folder/'audit_selected_dco_history_inputs.py']
        paths += [d/'waveform_assessment/assessment.json'for d in fitting+holdouts if d!=case]
        pins={str(p):sha(p)for p in paths};verify(pins);save(output/'inputs.json',dict(input_sha256=pins,wait_case=str(case),fitting=list(map(str,fitting)),holdouts=list(map(str,holdouts)),corner=corner,native_cases_launched=0,release_ready=False))
        deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+12600
        while True:
            state=json.loads((case/'status.json').read_text())['state']
            if state=='corner_detector_response_measured':break
            if state=='stopped_without_qualification'or identity(owner['pid'])!=owner['birth']:raise ValueError('original native corner probe stopped without complete response')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('native probe observation deadline; original unchanged')
            save(output/'status.json',dict(state='waiting_for_corner_raw_detector_probe',release_ready=False));time.sleep(10)
        verify(pins);command=['/usr/bin/apptainer','exec','--bind','/home:/home,/tmp:/tmp',image,'/usr/bin/python3',worker,'--corner',corner,'--output',output/'model']
        for d in fitting:command+=['--fit',d/'waveform_assessment/assessment.json']
        for d in holdouts:command+=['--holdout',d/'waveform_assessment/assessment.json']
        save(output/'status.json',dict(state='fitting_corner_raw_detector',release_ready=False))
        with lease(1,2,time.clock_gettime(time.CLOCK_BOOTTIME)+600):execute(command,output/'fit.log',time.clock_gettime(time.CLOCK_BOOTTIME)+600,2)
        verify(pins);receipt=output/'model/assessment.json';a=json.loads(receipt.read_text())
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(receipt):sha(receipt)},operating_point=a['operating_point'],all_sampled_signs_match=a['all_sampled_signs_match'],all_event_counts_match=a['all_event_counts_match'],all_edges_within_observed_fit_band=a['all_edges_within_observed_fit_band'],corner_sender_waveforms_correlated=False,diagnostic=True,native_interface_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='corner_raw_detector_fit_assessed',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),original_native_jobs_unchanged=True,release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in('case','output'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--fit',action='append',type=Path,required=True);p.add_argument('--holdout',action='append',type=Path,required=True);p.add_argument('--corner',choices=('ff','ss','sf','fs'),required=True);a=p.parse_args()
    run(a.case.resolve(),[p.resolve()for p in a.fit],[p.resolve()for p in a.holdout],a.corner,a.output.resolve())
