"""Assess all corrected tuning endpoints only after normal capture completion."""
import json,os,time
from runtime_common import ROOT,save,sha
from resources import identity,lease
from read_selected_standard import read_selected_standard
from check_contact_corrected_controls import assess


def verify(pins):
    for p,digest in pins.items():
        if sha(p)!=digest:raise ValueError('changed input/artifact: '+p)


def run():
    base=ROOT/'build/signoff400';output=base/'selected_keeper_contact_corrected_controls_1584'
    output.mkdir(exist_ok=False);save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())) )
    capture=base/'selected_keeper_contact_corrected_fine134_1581'
    coordinator=base/'selected_keeper_contact_corrected_transient_queue_1582'
    bindings=base/'selected_keeper_contact_control_bindings_1583';status=output/'status.json'
    try:
        binding_receipt=bindings/'assessment.json';br=json.loads(binding_receipt.read_text())
        verify(br['input_sha256']);verify(br['artifacts'])
        mapping=json.loads((bindings/'bindings.json').read_text());owner=json.loads((coordinator/'owner.json').read_text())
        deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+172800
        while True:
            if (capture/'status.json').exists():
                state=json.loads((capture/'status.json').read_text())['state']
                if state=='flat_native_programming_transient_complete' and (capture/'assessment.json').exists():break
                if state=='stopped_without_qualification':raise RuntimeError('capture stopped without qualification')
            if identity(owner['pid'])!=owner['birth']:raise RuntimeError('capture coordinator gone without completed reference')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('completed capture observation deadline')
            save(status,dict(state='waiting_for_completed_corrected_capture',release_ready=False));time.sleep(10)
        receipt=capture/'assessment.json';record=json.loads(receipt.read_text());inputs=capture/'inputs.json';domain=json.loads(inputs.read_text())
        verify(record['input_sha256']);verify(record['artifacts'])
        if (not record['normal_native_completion'] or not record['stationary_requested_code']
            or (domain['coarse'],domain['fine'])!=(23,134) or domain['simulation_ns']!=340
            or domain['reset_release_ns']!=80 or domain['capture_format']!='Xyce_standard_precision17'):
            raise ValueError('same completed corrected capture and scope required')
        model=base/'selected_keeper_contact_corrected_native_1579/model.spice'
        if record['input_sha256'].get(str(model))!=sha(model):raise ValueError('corrected native model lineage required')
        with lease(1,4,time.clock_gettime(time.CLOCK_BOOTTIME)+86400):
            save(status,dict(state='checking_completed_endpoint_voltages',release_ready=False))
            rows=read_selected_standard(capture/'transient.prn',mapping['roles'],340e-9)
            checks=assess(rows,mapping['observations'],23,134)
        if len(checks)!=604:raise ValueError('all 604 endpoints required')
        checkfile=output/'checks.json';save(checkfile,checks)
        save(output/'assessment.json',dict(input_sha256={str(p):sha(p) for p in [receipt,inputs,binding_receipt,bindings/'bindings.json',ROOT/'verification/signoff400/check_contact_corrected_controls.py',ROOT/'verification/signoff400/read_selected_standard.py',ROOT/'verification/signoff400/check_selected_boundary_waveforms.py',__file__]},
            artifacts={str(checkfile):sha(checkfile)},observed_endpoint_voltages=604,coarse=23,fine=134,window_ns=[280,340],
            all_macro_and_DCO_tuning_bits_match=all(c['passed'] for c in checks),
            physical_reset_timing_qualified=False,frequency_model_qualified=False,release_ready=False))
        save(status,dict(state='completed_corrected_physical_control_checks',passed=all(c['passed'] for c in checks),release_ready=False))
    except Exception as error:
        save(status,dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise

if __name__=='__main__':run()
