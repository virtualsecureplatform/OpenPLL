"""Validate zero junctions, physical body ties, geometry controls and numeric charge."""
import json,time,shlex
from pathlib import Path
from runtime_common import ROOT,save,sha
from resources import lease
from native_C_roundoff import assess
from native_C_passivity_v2 import assess_caps
from audit_keeper_native_R_contraction import parse

def origins(text):
    result={}
    for line in text.splitlines():
        if line.startswith('* OPENPLL_ORIGIN '):
            f=line.split();result[(f[3],int(f[4]),int(f[5]))]=f[2]
    return result

def run():
    b=ROOT/'build/signoff400';out=b/'selected_RC_repair_assessment_1670';out.mkdir(exist_ok=False)
    crop=b/'selected_crossplane_area_crop_1662';controls=b/'selected_optimized_RC_controls_1673';physical=b/'selected_zero_junction_origins_1659/assessment.json';passive=b/'selected_precise_C_passivity_1666/assessment.json'
    paths=[Path(__file__).resolve(),Path(__file__).with_name('native_C_roundoff.py'),Path(__file__).with_name('native_C_passivity_v2.py'),crop/'assessment.json',controls/'assessment.json',physical,passive]
    pins={str(p):sha(p) for p in paths};results=[]
    with lease(1,4,time.clock_gettime(time.CLOCK_BOOTTIME)+600):
        for directory in [crop,controls]:
            record=json.loads((directory/'assessment.json').read_text())
            for p,h in record['artifacts'].items():
                if sha(p)!=h:raise ValueError('completed control changed '+p)
        before=(crop/'before.spice').read_text();after=(crop/'after.spice').read_text();lookup=origins(before)
        before_data=parse(before);after_data=parse(after)
        names=lambda s:[l.split()[0] for l in s.splitlines() if l.startswith('X')]
        bdev=dict(zip(names(before),before_data['devices']));adev=dict(zip(names(after),after_data['devices']));virtual=[]
        for line in (crop/'RC_Area_Crop.ext').open():
            if not line.startswith('device '):continue
            f=shlex.split(line)
            if 'fet_' not in f[2]:continue
            j=7
            while '=' in f[j]:j+=1
            triples=f[j+1:]
            if len(triples)!=9:raise ValueError('native MOS terminal triples required')
            if triples[4]=='0' and triples[3]==f[j]:
                if triples[5]!='0,0':raise ValueError('fresh producer lost known-zero junction attributes')
                key=(f[2],int(f[3]),int(f[4]));name=lookup[key]
                if origins(after).get(key)!=name:raise ValueError('physical device identity changed')
                a,z=bdev[name],adev[name]
                if any(d[2].get(k)!=0 for d in [a,z] for k in ['as','ps']):raise ValueError('virtual source acquired junction geometry')
                if z[1][2]!=z[1][3]:raise ValueError('virtual source separated from physical bulk point')
                virtual.append(dict(instance=name,model=f[2],point=[int(f[3]),int(f[4])],source_and_bulk_node=z[1][2]))
        if len(virtual)<2:raise ValueError('both MOS polarities required in native virtual-source crop')
        for case in [crop,*sorted(p for p in controls.iterdir() if p.is_dir() and p.name.endswith('fixed1'))]:
            metrics=assess((case/'before.spice').read_text(),(case/'after.spice').read_text())
            log=(case/'native.log').read_text()
            bad=[prefix for prefix in ['OPENPLL_RC_BREAK_BOUNDS','OPENPLL_RC_NEGATIVE_AREA','OPENPLL_RC_BAD_AREA','OPENPLL_RC_BAD_CAP_BUDGET','OPENPLL_RC_EMPTY_CROSSPLANE_OVERLAP','OPENPLL_RC_EMPTY_DRIVER_OVERLAP'] if prefix in log]
            if bad or not metrics['native_devices_and_C_conserved']:raise ValueError('corrected native geometry/charge control failed')
            result=assess_caps(parse((case/'after.spice').read_text())['caps'])
            if not result['linear_C_PSD_certified']:raise ValueError('control C storage not certified')
            results.append(dict(case=str(case),charge=metrics,passivity=result))
        if not json.loads(passive.read_text())['linear_C_PSD_certified']:raise ValueError('whole-reference linear C certificate required')
        for p,h in pins.items():
            if sha(p)!=h:raise ValueError('repair assessment input changed')
        save(out/'assessment.json',dict(input_sha256=pins,virtual_source_geometry_and_body_ties_verified=virtual,all_five_geometry_and_charge_controls_pass=True,full_reference_linear_C_PSD=True,results=results,full_native_RC_pending=True,RC_export_fixed=False,release_ready=False))
if __name__=='__main__':run()
