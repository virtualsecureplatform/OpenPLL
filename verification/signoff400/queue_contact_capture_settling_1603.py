"""Assess predeclared settling windows only after completed physical controls."""
import json,os,time
from runtime_common import ROOT,save,sha
from resources import identity,lease
from read_selected_standard import read_selected_standard
from contact_capture_settling import assess_settling


def verify(record):
    for field in ['input_sha256','artifacts']:
        for path,digest in record.get(field,{}).items():
            if sha(path)!=digest:raise ValueError('completed receipt closure changed: '+path)


def run():
    base=ROOT/'build/signoff400';output=base/'selected_keeper_contact_capture_settling_1603';output.mkdir(exist_ok=False)
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())) )
    controls=base/'selected_keeper_contact_corrected_controls_1584';capture=base/'selected_keeper_contact_corrected_fine134_1581'
    owner=json.loads((controls/'owner.json').read_text());deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+172800
    try:
        while True:
            state=json.loads((controls/'status.json').read_text())['state']
            if state=='completed_corrected_physical_control_checks' and (controls/'assessment.json').exists():break
            if state=='stopped_without_qualification':raise RuntimeError('physical-control prerequisite stopped')
            if identity(owner['pid'])!=owner['birth']:raise RuntimeError('physical-control owner missing without completion')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('completed-control observation deadline')
            save(output/'status.json',dict(state='waiting_for_completed_physical_controls',release_ready=False));time.sleep(10)
        paths=[capture/'assessment.json',controls/'assessment.json'];cr,pr=[json.loads(p.read_text()) for p in paths]
        verify(cr);verify(pr)
        if not cr['normal_native_completion'] or not pr['all_macro_and_DCO_tuning_bits_match'] or pr['observed_endpoint_voltages']!=604:
            raise ValueError('completed native capture with all 604 matching endpoints required')
        if pr['input_sha256'].get(str(paths[0]))!=sha(paths[0]):raise ValueError('physical checks refer to a different capture')
        with lease(1,4,time.clock_gettime(time.CLOCK_BOOTTIME)+86400):
            save(output/'status.json',dict(state='assessing_completed_capture_windows',release_ready=False))
            rows=read_selected_standard(capture/'transient.prn',{'output':'PLLOUT'},340e-9)
            result=assess_settling(rows)
        save(output/'assessment.json',dict(input_sha256={str(p):sha(p) for p in [*paths,capture/'transient.prn',__file__,ROOT/'verification/signoff400/contact_capture_settling.py',ROOT/'verification/signoff400/read_selected_standard.py',ROOT/'verification/signoff400/assess_selected_isolated_control.py']},**result))
        save(output/'status.json',dict(state='completed_settling_screen',sample_stability_screen_pass=result['sample_stability_screen_pass'],release_ready=False))
    except Exception as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise

if __name__=='__main__':run()
