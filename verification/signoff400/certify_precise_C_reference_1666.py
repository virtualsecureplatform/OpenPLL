"""Completed-only passivity certificate for every explicit native linear C card."""
import json,time,resource
from pathlib import Path
from runtime_common import ROOT,save,sha
from resources import lease,identity
from native_C_passivity_v2 import assess_caps
from audit_keeper_native_R_contraction import number

def run():
    source=ROOT/'build/signoff400/selected_precise_C_reference_1664';out=ROOT/'build/signoff400/selected_precise_C_passivity_1666';out.mkdir(exist_ok=False)
    owner=json.loads((source/'owner.json').read_text());deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+7200
    save(out/'status.json',dict(state='waiting_for_live_C_reference',release_ready=False))
    try:
        while not (source/'assessment.json').exists():
            state=json.loads((source/'status.json').read_text())
            if state['state']=='stopped_without_qualification':raise RuntimeError(state)
            if identity(owner['pid'])!=owner['birth']:raise RuntimeError('C export ended without completion')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>deadline:raise TimeoutError('reference observation deadline')
            time.sleep(10)
        receipt=source/'assessment.json';r=json.loads(receipt.read_text());spice=source/'capacitance.spice'
        if r['artifacts'][str(spice)]!=sha(spice):raise ValueError('completed C source changed')
        pins={str(p):sha(p) for p in [receipt,spice,Path(__file__).resolve(),Path(__file__).with_name('native_C_passivity_v2.py'),Path(__file__).with_name('audit_keeper_native_R_contraction.py')]}
        with lease(1,8,deadline):
            resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
            save(out/'status.json',dict(state='certifying_complete_linear_C_operator',release_ready=False))
            caps=[]
            for line in spice.open():
                if line.startswith('C'):
                    f=line.split();caps.append((f[1],f[2],number(f[3])))
            result=assess_caps(caps)
            save(out/'passivity_report.json',result)
            for p,h in pins.items():
                if sha(p)!=h:raise ValueError('passivity input changed')
            save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(out/'passivity_report.json'):sha(out/'passivity_report.json')},all_explicit_native_C_cards_examined=len(caps),nonzero_C_cards=sum(v!=0 for a,b,v in caps),negative_C_cards=sum(v<0 for a,b,v in caps),linear_C_PSD_certified=result['linear_C_PSD_certified'],capacitors_modified=False,nonlinear_device_passivity_claimed=False,full_R_coverage=False,RC_export_fixed=False,release_ready=False))
        save(out/'status.json',dict(state='completed_linear_C_certificate',release_ready=False))
    except BaseException as e:
        save(out/'status.json',dict(state='stopped_without_qualification',reason=repr(e),release_ready=False));raise
if __name__=='__main__':run()
