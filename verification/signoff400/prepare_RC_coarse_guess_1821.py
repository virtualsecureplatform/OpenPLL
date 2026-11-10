"""Prepare the proven ideal-wire reference solely for a full-RC Newton initial guess."""
import json,time,os
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import lease
from prepare_reference_alias_native_RC_1768 import normalize
from zero_C_placeholders_1809 import adapt

def run():
    os.sched_setaffinity(0,{22});base=ROOT/'build/signoff400';producer=base/'selected_reference_alias_full_RC_1764/assessment.json';r=json.loads(producer.read_text());verify(r['artifacts'])
    audit=base/'selected_reference_alias_full_RC_audit_1766/assessment.json';a=json.loads(audit.read_text());verify(a['input_sha256']);verify(a['artifacts'])
    if not a['all_full_RC_checks_pass']:raise ValueError('full charge/physical contraction audit required')
    source=producer.parent/'before.spice'
    if a['input_sha256'].get(str(source))!=sha(source):raise ValueError('audited ideal-wire source required')
    out=base/'selected_RC_coarse_guess_model_1821';out.mkdir(exist_ok=False)
    paths=[producer,audit,source,Path(__file__).resolve(),Path(__file__).with_name('prepare_reference_alias_native_RC_1768.py'),Path(__file__).with_name('zero_C_placeholders_1809.py')];pins={str(p):sha(p)for p in paths}
    with lease(1,12,time.clock_gettime(time.CLOCK_BOOTTIME)+600):
        text,nodes,metrics=normalize(source.read_text());model,zeros=adapt(text)
        if metrics['source_counts']['X']!=62338:raise ValueError('complete physical device population required')
        path=out/'model.spice';path.write_text(model);mapping=out/'nodes.json';save(mapping,nodes);verify(pins)
        save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p)for p in [path,mapping]},normalization=metrics,zero_C_adapter=zeros,purpose='initial guess only for the unchanged full RC circuit',distributed_wire_R_included=False,full_RC_qualified=False,release_ready=False))
if __name__=='__main__':run()
