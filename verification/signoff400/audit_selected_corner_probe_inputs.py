"""Verify conditional corner probes change only PDK selection and observations."""
import argparse,json,re
from pathlib import Path
from common_v3 import save,sha,verify
from compare_selected_dco_load_controls import canonical_deck


def body(folder):
    text=canonical_deck((folder/'control.spice').read_text())
    text,count=re.subn(r'(?m)^(\.lib .+) (tt|ff|ss|sf|fs)$',r'\1 <CORNER>',text)
    if count!=1:raise ValueError('one explicit PDK corner required')
    return '\n'.join(l for l in text.splitlines() if not l.startswith('.print '))


def run(baseline,cases,output):
    if output.exists():raise FileExistsError(output)
    b=json.loads((baseline/'manifest.json').read_text());verify(b['input_sha256'])
    records=[];pins={str(p):sha(p) for p in [baseline/'manifest.json',Path(__file__).resolve(),Path(__file__).with_name('compare_selected_dco_load_controls.py')]}
    for case in cases:
        m=json.loads((case/'manifest.json').read_text());verify(m['input_sha256'])
        if sha(case/'devices.spice')!=sha(baseline/'devices.spice') or sha(case/'sources.spice')!=sha(baseline/'sources.spice'):raise ValueError('physical cards or prescribed voltages changed')
        if body(case)!=body(baseline):raise ValueError('native deck physics or solver changed beyond corner')
        corner=m['operating_point']['corner']
        libs=re.findall(r'^\.lib .+ (tt|ff|ss|sf|fs)$',(case/'control.spice').read_text(),re.MULTILINE)
        if libs!=[corner] or corner=='tt':raise ValueError('matching explicit non-TT device corner required')
        if m['exterior_bias_source_operating_point']!=b['operating_point'] or m['full_corner_exterior_bias_qualified'] is not False:raise ValueError('TT exterior-bias limitation must remain explicit')
        if m['controls']!=b['controls'] or list(m['observed_roles'].items())[:len(b['observed_roles'])]!=list(b['observed_roles'].items()):raise ValueError('programming or original observations changed')
        if len(m['observed_roles'])!=len(b['observed_roles'])+5:raise ValueError('five retained clock observations required')
        for n in ['manifest.json','devices.spice','sources.spice','control.spice']:pins[str(case/n)]=sha(case/n)
        records.append(dict(case=str(case),retained_device_corner=corner,exterior_bias_corner='tt',physical_device_and_source_files_identical=True,only_corner_and_observation_coverage_changed=True,full_corner_exterior_bias_qualified=False))
    verify(pins);save(output,dict(input_sha256=pins,records=records,physical_models_qualified=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--case',type=Path,action='append',required=True)
    for n in ['baseline','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.baseline.resolve(),[p.resolve() for p in a.case],a.output.resolve())
