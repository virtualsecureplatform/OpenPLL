"""Compare an original clock-cone control after native/reference observation ends."""
import argparse,json,os,subprocess,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease
from assess_selected_detector_prefix import read_prefix
from compare_selected_dco_startup_aligned_v2 import aligned,window_frequency


def run(native,baseline,reference,provenance,prepared,preflight,output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{28})
    folder=Path(__file__).resolve().parent;checker=folder/'compare_selected_dco_startup_aligned_v2.py'
    owners=[json.loads((p/'owner.json').read_text()) for p in [native,provenance]]
    pins={str(p):sha(p) for p in [Path(__file__).resolve(),checker,preflight,prepared/'manifest.json',baseline/'manifest.json',baseline/'assessment.json',folder/'assess_selected_detector_prefix.py']}
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    save(output/'inputs.json',dict(input_sha256=pins,original_owners=owners,automatic_native_launch=False,release_ready=False))
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+12600
    try:
        while True:
            pending=[]
            for p,owner,terminal in zip([native,provenance],owners,['real_driver_DCO_diagnostic_complete','retained_native_reference_provenance_captured']):
                state=json.loads((p/'status.json').read_text())['state']
                if state==terminal:continue
                if state=='stopped_without_qualification' or identity(owner['pid'])!=owner['birth']:raise RuntimeError('original control/observation stopped before completion: '+str(p))
                pending.append(str(p))
            if not pending:break
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('observer deadline; original native jobs untouched')
            save(output/'status.json',dict(state='waiting_for_original_clock_control_and_reference',pending=pending,release_ready=False));time.sleep(10)
        verify(pins)
        proof=json.loads(preflight.read_text());verify(proof['input_sha256'])
        m=json.loads((native/'manifest.json').read_text());verify(m['input_sha256'])
        for name in ['devices.spice','sources.spice']:
            if m['input_sha256'].get(str(native/name))!=sha(prepared/name):raise ValueError('actual native circuit differs from preflight')
        waves=[]
        with lease(1,2,deadline):
            for p in [baseline,native]:
                mm=json.loads((p/'manifest.json').read_text());verify(mm['input_sha256'])
                worker=json.loads((p/'native.process.json').read_text())
                if identity(worker['pid'])==worker['birth']:raise ValueError('original native worker still live')
                rows,info=read_prefix(p/'control.raw',mm['observed_roles'])
                if info['declared_samples']!=len(rows) or info['incomplete_final_sample_discarded'] or abs(rows[-1][0]-60e-9)>1e-18:raise ValueError('complete native 60 ns observations required')
                edges,startup=aligned(rows,1,2);waves.append(edges)
            comparisons={}
            for name,start,stop in [('common',10,40),('early',10,25),('late',25,40)]:
                a,b=[window_frequency(w,start,stop) for w in waves]
                comparisons[name]=dict(window_after_first_rise_ns=[start,stop],baseline=a,clock_expanded=b,difference_ppm=1e6*(b['frequency_mhz']/a['frequency_mhz']-1))
            command=['/usr/bin/python3',checker,'--native',native,'--reference',reference/'waveform_assessment/signals.csv','--reference-assessment',reference/'waveform_assessment/assessment.json','--reference-provenance',provenance/'provenance.json','--output',output/'full_reference_comparison']
            with (output/'full_reference.log').open('x') as log:subprocess.run(list(map(str,command)),stdout=log,stderr=subprocess.STDOUT,check=True,timeout=1800)
        verify(pins)
        artifacts={str(p):sha(p) for p in [native/'control.raw',baseline/'control.raw',output/'full_reference_comparison'] if p.is_file()}
        report=output/'full_reference_comparison';artifacts[str(report)]=sha(report)
        save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,baseline_comparisons=comparisons,
            frequency_correlation_qualified=False,full_boundary_forcing_covered=False,physical_models_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='coherent_clock_control_compared',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['native','baseline','reference','provenance','prepared','preflight','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['native','baseline','reference','provenance','prepared','preflight','output']))
