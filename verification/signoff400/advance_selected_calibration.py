"""Attach a completed same-circuit native point and request the next measurement.

Only startup fine biases and RAW output location may differ from the reference
native deck. This never interpolates a tuning table or qualifies physical models.
"""
import argparse,json,os,re,time
from pathlib import Path
from common_v3 import save,sha,verify
from resources import identity,lease
from run_selected_mixed_signal import measured_point
from selected_model_registry import create,validate
from select_calibration_point import choose


def normalized_deck(text):
    fine={};lines=[]
    for line in text.splitlines():
        match=re.fullmatch(r'(V\S+\s+STARTUP_FINE\[(\d+)\]\s+0\s+)(\S+)\s*',line,re.IGNORECASE)
        if match:
            bit=int(match[2]);value=float(match[3])
            if bit in fine or bit not in range(8) or value not in (0.,1.8):raise ValueError('unique binary eight-bit startup fine sources required')
            fine[bit]=value==1.8;line=match[1]+'<fine>'
        elif line.lstrip().upper().startswith('.PRINT '):
            line,count=re.subn(r'\bFILE=\S+','FILE=<output>',line,flags=re.IGNORECASE)
            if count!=1:raise ValueError('one RAW print output required')
        lines.append(line)
    if len(fine)!=8:raise ValueError('all eight startup fine biases required')
    return '\n'.join(lines),sum(int(v)<<k for k,v in fine.items())


def compare_decks(base,target,expected_fine):
    a,old=normalized_deck(base);b,new=normalized_deck(target)
    if a!=b:raise ValueError('native calibration changed more than startup fine and RAW destination')
    if new!=expected_fine:raise ValueError('native stimulus does not match measured fine code')
    return dict(reference_fine=old,new_fine=new,only_fine_bias_and_RAW_destination_changed=True)


def advance(registry_path,base_native,native,assessment,output):
    output.mkdir(parents=True,exist_ok=False)
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    watcher=json.loads((assessment/'owner.json').read_text())
    deadline=json.loads((native/'status.json').read_text()).get('native_deadline_uptime',time.clock_gettime(time.CLOCK_BOOTTIME))+3600
    paths=[registry_path,Path(__file__).resolve(),Path(__file__).with_name('selected_model_registry.py'),
           Path(__file__).with_name('run_selected_mixed_signal.py'),Path(__file__).with_name('select_calibration_point.py')]
    pins={str(p):sha(p) for p in paths}
    save(output/'inputs.json',dict(input_sha256=pins,assessment_owner=watcher,release_ready=False))
    try:
        while True:
            state=json.loads((assessment/'status.json').read_text())['state']
            if state=='calibration_waveform_assessed':break
            if state=='stopped_without_qualification':raise RuntimeError('native assessment failed')
            if identity(watcher['pid'])!=watcher['birth']:raise RuntimeError('assessment owner exited without completed calibration receipt')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>deadline:raise TimeoutError('calibration assessment wait exhausted')
            save(output/'status.json',dict(state='waiting_for_completed_calibration',release_ready=False));time.sleep(10)
        verify(pins)
        os.sched_setaffinity(0,{28})
        with lease(1,2,deadline):
            base=validate(json.loads(registry_path.read_text()))
            provenance=json.loads((assessment/'provenance.json').read_text())
            verify(provenance['input_sha256']);verify(provenance['native_input_sha256']);verify(provenance['artifacts'])
            manifest=json.loads((native/'manifest.json').read_text());verify(manifest['input_sha256'])
            base_manifest=json.loads((base_native/'manifest.json').read_text())
            for deck,owner in [(base_native/'profile.spice',base_manifest),(native/'profile.spice',manifest)]:
                if owner['input_sha256'].get(str(deck))!=sha(deck):raise ValueError('native deck is not pinned by its manifest')
            if base['analog']['input_sha256'].get(str(base_native/'manifest.json'))!=sha(base_native/'manifest.json'):
                raise ValueError('reference native manifest must belong to analog identity')
            models={k:v for k,v in base['analog']['input_sha256'].items() if k.endswith('.spice')}
            if not models or any(manifest['input_sha256'].get(k)!=v for k,v in models.items()):raise ValueError('native analog model identity changed')
            receipt=assessment/'assessment.json';coarse,fine,_=measured_point(receipt)
            if manifest['startup_fine']!=fine:raise ValueError('measured fine does not match native request')
            check=compare_decks((base_native/'profile.spice').read_text(),(native/'profile.spice').read_text(),fine)
            if sha(native/'profile.raw')!=provenance['raw_sha256']:raise ValueError('native waveform changed after assessment')
            receipts=[Path(row['receipt']) for row in base['points']]+[receipt]
            registry=create(base['analog'],base['interface'],receipts,output/'models.json')
            if registry['analog_key']!=base['analog_key'] or registry['interface_key']!=base['interface_key']:raise ValueError('calibration attachment changed model-domain identity')
            request=choose(registry['points'],coarse=coarse);save(output/'next_point.json',request)
        verify(pins)
        inputs={str(p):sha(p) for p in [registry_path,base_native/'manifest.json',native/'manifest.json',assessment/'provenance.json',receipt,Path(__file__).resolve()]}
        save(output/'assessment.json',dict(input_sha256=inputs,deck_comparison=check,
            measured_coarse=coarse,measured_fine=fine,measured_points=len(registry['points']),next_point=request,
            artifacts={str(p):sha(p) for p in [output/'models.json',output/'next_point.json']},
            analog_identity_preserved=True,interface_identity_preserved=True,physical_models_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='calibration_attached_next_measurement_requested',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['registry','base-native','native','assessment','output']:p.add_argument('--'+key,required=True,type=Path)
    a=p.parse_args();advance(*(getattr(a,k).resolve() for k in ['registry','base_native','native','assessment','output']))
