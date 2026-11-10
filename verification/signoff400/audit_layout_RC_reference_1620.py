"""Completed-only independent electrical conservation audit of the two-net pilot."""
import json,time,resource
from runtime_common import ROOT,save,sha
from resources import lease,identity
from audit_keeper_native_R_contraction import compare

def run():
    source=ROOT/'build/signoff400/selected_layout_RC_reference_1618'
    out=ROOT/'build/signoff400/selected_layout_RC_reference_audit_1620';out.mkdir(exist_ok=False)
    owner=json.loads((source/'owner.json').read_text());deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+5400
    save(out/'status.json',dict(state='waiting_for_live_native_pilot',release_ready=False))
    while not (source/'assessment.json').exists():
        state=json.loads((source/'status.json').read_text())
        if state['state']=='stopped_without_qualification':raise RuntimeError(state)
        if identity(owner['pid'])!=owner['birth']:raise RuntimeError('native pilot owner gone without completion')
        if time.clock_gettime(time.CLOCK_BOOTTIME)>deadline:raise TimeoutError('observation deadline')
        time.sleep(10)
    receipt=source/'assessment.json';r=json.loads(receipt.read_text())
    if not r['native_process_completed']:raise ValueError('completed native pilot required')
    pins={**r['input_sha256'],**r['artifacts'],str(receipt):sha(receipt),str(__file__):sha(__file__)}
    with lease(1,12,deadline):
        resource.setrlimit(resource.RLIMIT_AS,(12*1024**3,12*1024**3))
        save(out/'status.json',dict(state='auditing_completed_exports',release_ready=False))
        for p,h in pins.items():
            if sha(p)!=h:raise ValueError('changed input '+p)
        metrics=compare((source/'before.spice').read_text(),(source/'after.spice').read_text())
        save(out/'assessment.json',dict(input_sha256=pins,contraction=metrics,full_layout_R_coverage=False,distributed_C_placement_qualified=False,RC_export_fixed=False,release_ready=False))
    save(out/'status.json',dict(state='completed_native_pilot_audit',release_ready=False))
if __name__=='__main__':run()
