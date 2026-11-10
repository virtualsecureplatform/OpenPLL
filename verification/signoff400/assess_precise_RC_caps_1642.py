"""Independent completed-only charge checks for precise native RC controls."""
import json,time
from pathlib import Path
from fractions import Fraction as F
from runtime_common import ROOT,save,sha
from resources import lease
from native_C_roundoff import assess

def run():
    b=ROOT/'build/signoff400';out=b/'selected_precise_RC_caps_assessment_1642';out.mkdir(exist_ok=False)
    directories=[b/n for n in ['selected_cropped_precise_RC_caps_1639','selected_precise_RC_alias_paths_1640','selected_precise_subatto_cap_export_1641']]
    pins={str(p):sha(p) for p in [Path(__file__).resolve(),Path(__file__).with_name('native_C_roundoff.py'),Path(__file__).with_name('audit_keeper_native_R_contraction.py'),Path(__file__).with_name('compare_native_R_with_aliases.py')]};results=[]
    with lease(1,4,time.clock_gettime(time.CLOCK_BOOTTIME)+600):
        for base in directories:
            receipt=base/'assessment.json';record=json.loads(receipt.read_text());pins[str(receipt)]=sha(receipt)
            for p,h in record['artifacts'].items():
                if sha(p)!=h:raise ValueError('completed native artifact changed: '+p)
            cases=[base] if base!=directories[1] else sorted(p for p in base.iterdir() if p.is_dir())
            if base==directories[2]:continue
            for case in cases:
                metrics=assess((case/'before.spice').read_text(),(case/'after.spice').read_text())
                results.append(dict(case=str(case),metrics=metrics))
        tiny=json.loads((directories[2]/'assessment.json').read_text())
        actual=[F(v) for a,b,v in tiny['before_capacitors'] if {a,b}=={'a#','b'}]
        target=F(1,4*10**18)
        tiny_ok=len(actual)==1 and actual[0]>0 and abs(actual[0]-target)<=4*F(1,2**52)*target
        if not tiny_ok:raise ValueError('sub-attofarad literal was lost or mis-scaled')
        if not all(r['metrics']['native_devices_and_C_conserved'] for r in results):raise ValueError('native C conservation outside float64 operation bound')
        for p,h in pins.items():
            if sha(p)!=h:raise ValueError('audit input changed')
        save(out/'assessment.json',dict(input_sha256=pins,results=results,subatto_cap_preserved=True,subatto_expected_F_exact=str(target),subatto_observed_F_exact=str(actual[0]),all_control_device_and_C_checks_pass=True,no_absolute_roundoff_floor=True,full_network_coverage_verified=False,RC_export_fixed=False,release_ready=False))
if __name__=='__main__':run()
