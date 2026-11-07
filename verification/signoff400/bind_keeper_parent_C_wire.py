"""Bind fresh parent wire terminals directly to the full capacitance hierarchy."""
import argparse,json,re,os,time
from pathlib import Path
from common_v3 import save,sha,verify
from bind_prototype_spef_pins_v2 import bind
from resources import lease,identity


def run(extraction,rc,binding,output):
    receipts=[p/'assessment.json'for p in [extraction,rc,binding]];e,r,b=records=[json.loads(p.read_text())for p in receipts]
    for a in records:verify(a['input_sha256']);verify(a['artifacts'])
    layout=[Path(p)for p in e['input_sha256']if p.endswith('/assessment.json')and 'checked_filled_parent'in p]
    if len(layout)!=2:raise ValueError('checked layout plus LVS proof required')
    for p in layout:
        if r['input_sha256'].get(str(p))!=sha(p):raise ValueError('wire and full C layout differs')
    raw=next(extraction.glob('*/capacitance.spice'));join=binding/'join.json'
    if not e['full_checked_parent_capacitance_extracted']or not b['all_RC_terminals_bound_and_connected']:raise ValueError('completed same-layout C and wire binding required')
    if b['input_sha256'].get(str(receipts[1]))!=sha(receipts[1]):raise ValueError('wire binding from another extraction')
    mapping={re.sub(r'\\(.)',r'\1',row['routed_instance']):row['extracted_instance']for row in json.loads(join.read_text())['mapping']}
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{25});save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    files=[*receipts,raw,join,Path(__file__).resolve(),Path(__file__).with_name('bind_prototype_spef_pins_v2.py')];pins={str(p):sha(p)for p in files};artifacts={};results=[]
    text=raw.read_text()
    with lease(1,8,time.clock_gettime(time.CLOCK_BOOTTIME)+600):
        for corner in ['min','nom','max']:
            parsed=rc/(corner+'.json');pins[str(parsed)]=sha(parsed)
            if r['artifacts'].get(str(parsed))!=sha(parsed):raise ValueError('parsed wire view changed')
            result=bind(json.loads(parsed.read_text()),text,raw.parent.name,mapping);target=output/(corner+'.binding.json');save(target,result);artifacts[str(target)]=sha(target)
            results.append(dict(corner=corner,networks=len(result['networks']),failures=len(result['failures']),all_RC_terminals_bound_and_connected=result['all_RC_terminals_bound_and_connected']))
    verify(pins);save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,results=results,full_C_hierarchy_bound_to_fresh_parent_wire=all(x['all_RC_terminals_bound_and_connected']for x in results),capacitance_modified=False,wire_R_inserted=False,parent_loading_complete=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['extraction','rc','binding','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve()for n in ['extraction','rc','binding','output']))
