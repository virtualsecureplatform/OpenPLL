"""Check keeper antenna qualification rejects mismatched and nonpassing evidence."""
import argparse,json
from pathlib import Path
from common_v3 import save,sha,verify
from qualify_keeper_antenna_component import run


def check(qualification,output):
    q=json.loads(qualification.read_text());verify(q['input_sha256']);verify(q['artifacts'])
    evidence=qualification.parent/'evidence.json';paths=[Path(p)for p in json.loads(evidence.read_text())['receipts']]
    if len(paths)!=9:raise ValueError('nine component authorities required')
    output.mkdir(parents=True,exist_ok=False);results=[]
    cases=[('old_GDS',1,'selected_GDS_sha256','71dc786409f1c59279f6d29896df666446b1fe7f3a3d4bab32efe5e7f234cb63','exact selected GDS'),('wrong_inventory',1,'expected_native_MOS_count',61616,'registered keeper inventory'),('nonzero_feedback',5,'native_antenna_feedback_entries',1,'completed zero-feedback'),('missing_stage_guard',8,'current_stage_components_not_joined_by_future_stubs',False,'independent current-stage')]
    for name,index,key,value,reason in cases:
        case=output/name;case.mkdir();data=json.loads(paths[index].read_text());data[key]=value;mutation=case/'mutated.json';save(mutation,data);args=list(paths);args[index]=mutation
        try:run(*args,case/'result')
        except ValueError as error:
            if reason not in str(error):raise ValueError('unexpected rejection: '+str(error))
            results.append(dict(case=name,rejected=True,reason=str(error)))
        else:raise ValueError('invalid antenna evidence accepted: '+name)
    files=[qualification,evidence,*paths,Path(__file__).resolve(),Path(__file__).with_name('qualify_keeper_antenna_component.py')]
    save(output/'assessment.json',dict(input_sha256={str(p):sha(p)for p in files},artifacts={},results=results,all_four_negative_controls_rejected=True,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--qualification',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();check(a.qualification.resolve(),a.output.resolve())
