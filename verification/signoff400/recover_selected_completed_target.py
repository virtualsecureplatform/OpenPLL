"""Publish a new continuation from completed target evidence; never rerun native."""
import argparse,json,os
from pathlib import Path
from common_v3 import save,sha,verify
from resources import identity
from selected_model_registry import validate


def require_completed(status,native,assessment,binding):
    if status.get('state')!='stopped_without_qualification' or status.get('reason')!="FileNotFoundError(2, 'No such file or directory')":
        raise ValueError('original recorded postprocessing namespace failure required')
    if native.get('state')!='native_startup_completed_waveform_assessment_pending':
        raise ValueError('normal native completion required')
    if assessment.get('end_ns')!=260 or assessment.get('samples',0)<=0:
        raise ValueError('complete assessed 260 ns waveform required')
    if binding.get('analog_cache_key_unchanged')is not True or binding.get('measured_points_retained')!=5:
        raise ValueError('same five measured points and unchanged analog identity required')


def run(original,binding,output):
    if output.exists():raise FileExistsError(output)
    read=lambda p:json.loads(p.read_text())
    state=read(original/'status.json');native=read(original/'native/status.json')
    measured=read(original/'waveform_assessment/assessment.json');bound=read(binding/'assessment.json')
    require_completed(state,native,measured,bound)
    # Run inside the pinned CAD namespace: historical receipts include Icarus/PDK.
    inputs=read(original/'inputs.json');verify(inputs['input_sha256'])
    provenance=read(original/'waveform_assessment/provenance.json')
    for key in ['input_sha256','native_input_sha256','artifacts']:verify(provenance[key])
    if sha(original/'native/profile.raw')!=provenance['raw_sha256']:raise ValueError('completed RAW changed')
    registry_receipt=read(original/'registry/assessment.json')
    for receipt in [registry_receipt,bound]:
        verify(receipt['input_sha256']);verify(receipt['artifacts'])
    old=validate(read(original/'registry/models.json'));new=validate(read(binding/'models.json'))
    if old['analog_key']!=new['analog_key'] or old['points']!=new['points']:
        raise ValueError('binding must retain original analog identity and every measured point')
    files=[original/'status.json',original/'inputs.json',original/'request.json',original/'native/status.json',original/'waveform_assessment/provenance.json',original/'waveform_assessment/assessment.json',original/'registry/assessment.json',original/'registry/models.json',binding/'assessment.json',binding/'models.json',Path(__file__).resolve(),Path(__file__).with_name('common_v3.py')]
    pins={str(p):sha(p)for p in files};verify(pins)
    output.mkdir();save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())) )
    for name,target in [('native',original/'native'),('waveform_assessment',original/'waveform_assessment'),('registry',original/'registry'),('selected_interface',binding)]:
        (output/name).symlink_to(target,target_is_directory=True)
    save(output/'request.json',read(original/'request.json'))
    save(output/'assessment.json',dict(input_sha256=pins,original_failed_pipeline=str(original),measured_target_request=read(original/'request.json'),mean_frequency_mhz=measured['signals']['v(pllout)']['mean_frequency_mhz'],completed_RAW_hash_verified=True,original_failure_receipts_preserved=True,new_native_cases=0,diagnostic=True,release_ready=False))
    save(output/'status.json',dict(state='target_refinement_native_point_attached',recovered_postprocessing_only=True,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['original','binding','output']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(a.original.resolve(),a.binding.resolve(),a.output.resolve())
