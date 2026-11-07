"""Reject mismatched corner and unbound model relocation before native launch."""
import argparse,copy,json,shutil
from pathlib import Path
from common_v3 import save,sha,verify
from follow_selected_matching_sender_holdouts import preflight


def run(protocol,output):
    if output.exists():raise FileExistsError(output)
    original=json.loads(protocol.read_text());verify(original['input_sha256']);output.mkdir(parents=True)
    records=[];artifacts={}
    for name in ['wrong_corner_fit','unbound_relocated_fit']:
        folder=output/name;folder.mkdir();mutant=copy.deepcopy(original)
        if name=='wrong_corner_fit':mutant['fits']['ff']=mutant['fits']['ss']
        else:
            fake=folder/'fake_sf';fake.mkdir();source=Path(mutant['fits']['sf'])
            for filename in ['assessment.json','parameters.json','detector.v']:
                destination=fake/filename;shutil.copyfile(source/filename,destination);artifacts[str(destination)]=sha(destination)
            mutant['fits']['sf']=str(fake)
        test=folder/'protocol.json';save(test,mutant);attempt=folder/'unexpected_preflight.json'
        try:preflight(test,attempt)
        except ValueError as error:reason=str(error)
        else:raise AssertionError('invalid fit binding was accepted')
        expected='corner differs'if name=='wrong_corner_fit'else'bind unchanged'
        if expected not in reason or attempt.exists():raise AssertionError('expected early binding rejection without output')
        records.append(dict(control=name,rejected=True,reason=reason,preflight_output_created=False,native_jobs_launched=0));artifacts[str(test)]=sha(test)
    verify(original['input_sha256'])
    files=[protocol,Path(__file__).resolve(),Path(__file__).with_name('follow_selected_matching_sender_holdouts.py'),Path(__file__).with_name('common_v3.py')]
    save(output/'assessment.json',dict(input_sha256={str(p):sha(p)for p in files},artifacts=artifacts,controls=records,all_two_binding_controls_rejected=True,native_jobs_launched=0,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['protocol','output']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(a.protocol.resolve(),a.output.resolve())
