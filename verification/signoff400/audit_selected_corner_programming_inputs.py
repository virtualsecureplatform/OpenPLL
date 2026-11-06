"""Allow only declared physical programming changes and explicit PDK corner selection."""
import argparse,json,re
from pathlib import Path
from common_v3 import save,sha,verify
from audit_selected_dco_history_inputs import sources
from compare_selected_dco_load_controls import canonical_deck
from run_selected_dco_real_driver_control_v4 import programming_sources
from selected_spice_device_conditions import read


def body(path):
    text=canonical_deck(path.read_text());text,count=re.subn(r'(?m)^(\.lib .+) (tt|ff|ss|sf|fs)$',r'\1 <CORNER>',text)
    if count!=1:raise ValueError('one explicit device corner required')
    return text


def run(baseline,cases,inventory,output):
    if output.exists():raise FileExistsError(output)
    b=json.loads((baseline/'manifest.json').read_text());iv=json.loads(inventory.read_text());verify(b['input_sha256']);verify(iv['input_sha256'])
    old=programming_sources(iv['controls'],b['controls']['coarse'],b['controls']['fine']);x=sources(baseline/'sources.spice');records=[]
    files=[inventory,Path(__file__).resolve(),Path(__file__).with_name('run_selected_dco_real_driver_control_v4.py'),Path(__file__).with_name('compare_selected_dco_load_controls.py'),Path(__file__).with_name('selected_spice_device_conditions.py'),Path(__file__).with_name('audit_selected_dco_history_inputs.py')]
    for case in cases:
        m=json.loads((case/'manifest.json').read_text());verify(m['input_sha256']);new=programming_sources(iv['controls'],m['controls']['coarse'],m['controls']['fine']);expected={n for n in old if old[n]!=new[n]};y=sources(case/'sources.spice')
        if set(x)!=set(y) or {n for n in x if x[n][1]!=y[n][1]}!=expected:raise ValueError('unexpected prescribed source change')
        if any(float(y[n][1])!=v for n,v in new.items()):raise ValueError('physical programming driver input differs from declared code')
        if (baseline/'devices.spice').read_bytes()!=(case/'devices.spice').read_bytes():raise ValueError('physical device/passive cards changed')
        if body(baseline/'control.spice')!=body(case/'control.spice'):raise ValueError('solver or observation protocol changed')
        if read(case/'control.spice')['corner']!=m['operating_point']['corner']:raise ValueError('declared corner differs from device models')
        if m['observed_roles']!=b['observed_roles'] or m['exterior_bias_source_operating_point']!=b['exterior_bias_source_operating_point'] or m['full_corner_exterior_bias_qualified'] is not False:raise ValueError('physical observations or exterior-bias scope changed')
        records.append(dict(case=str(case),corner=m['operating_point']['corner'],controls=m['controls'],changed_programming_source_nodes=sorted(expected),same_device_cards_and_common_exterior_bias=True,only_programming_and_PDK_corner_changed=True))
        files += [case/n for n in ['manifest.json','devices.spice','sources.spice','control.spice']]
    files += [baseline/n for n in ['manifest.json','devices.spice','sources.spice','control.spice']]
    save(output,dict(input_sha256={str(p):sha(p) for p in files},records=records,full_corner_calibration_qualified=False,release_ready=False));print('audited target guides',len(records))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--case',type=Path,action='append',required=True)
    for n in ['baseline','inventory','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.baseline.resolve(),[p.resolve() for p in a.case],a.inventory.resolve(),a.output.resolve())
