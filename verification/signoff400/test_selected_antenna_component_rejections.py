"""Metadata rejection controls for the actual selected antenna qualifier.

Copies only metadata into fresh test directories. Does not launch CAD or
modify native artifacts. Synthetic controls cannot qualify hardware.
"""
import argparse,json
from pathlib import Path
from common_v3 import save,sha
from qualify_selected_antenna_component_v3 import run

NAMES=['manifest','tool-profile','build','rule-controls','diode-control','parent','geometry','paint-proof','process-audit']


def test(paths,qualification,output):
    output.mkdir(parents=True,exist_ok=False)
    positive=json.loads(qualification.read_text());module=Path(__file__).with_name('qualify_selected_antenna_component_v3.py').resolve()
    if positive.get('status')!='pass' or positive['input_sha256'].get(str(module))!=sha(module):raise ValueError('passing result from exact tested qualifier required')
    before={str(p):sha(p) for p in paths}
    if any(positive['input_sha256'].get(p)!=d for p,d in before.items()):raise ValueError('same native qualification inputs required')
    results=[]
    def rejected(name,arguments,expected):
        dest=output/(name+'_result')
        try:run(*arguments,dest)
        except ValueError as error:
            if expected not in str(error):raise AssertionError('unexpected rejection: '+str(error))
            if (dest/'qualification.json').exists():raise AssertionError('qualification emitted for invalid evidence')
            results.append(dict(case=name,rejected=True,reason=str(error)))
        else:raise AssertionError('invalid evidence accepted: '+name)
    # Preserve stale all-seven success flags but remove an actual process row.
    data=json.loads(paths[8].read_text());stages=json.loads((paths[8].parent/'stages.json').read_text());stage_dir=output/'missing_stage';stage_dir.mkdir()
    changed=stage_dir/'stages.json';save(changed,stages[:-1]);data['artifacts']={str(changed):sha(changed)};audit=stage_dir/'assessment.json';save(audit,data)
    arguments=list(paths);arguments[8]=audit;rejected('missing_actual_stage',arguments,'all seven current process layers required')
    # A claimed source-verified build must still be the build used by controls.
    data=json.loads(paths[2].read_text());binary=next(p for p in data['artifacts'] if p.endswith('/install/bin/magic'));data['artifacts'][binary]='0'*64
    changed=output/'different_build.json';save(changed,data);arguments=list(paths);arguments[2]=changed;rejected('mixed_installed_tool',arguments,'conflicting evidence identity')
    # Existing pass flags cannot carry qualification to another physical candidate.
    data=json.loads(paths[1].read_text());data['selected_GDS_sha256']='0'*64;changed=output/'different_candidate.json';save(changed,data)
    arguments=list(paths);arguments[1]=changed;rejected('wrong_GDS_profile',arguments,'exact selected GDS and native parent required')
    if any(sha(Path(p))!=d for p,d in before.items()):raise AssertionError('original qualification input changed')
    files={str(Path(__file__).resolve()):sha(Path(__file__)),str(qualification):sha(qualification),str(module):sha(module),**before}
    save(output/'assessment.json',dict(input_sha256=files,records=results,all_three_rejection_controls_pass=True,native_inputs_unchanged=True,synthetic=True,diagnostic=True,hardware_qualification=False,release_ready=False))
    print('three antenna qualifier rejection controls pass')

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in NAMES+['qualification','output']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();test([getattr(a,n.replace('-','_')).resolve() for n in NAMES],a.qualification.resolve(),a.output.resolve())
