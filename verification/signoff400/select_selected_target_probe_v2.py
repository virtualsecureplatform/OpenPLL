"""Narrow a measured conditional bracket, or retain a measured nominal target.

No predicted frequency enters a calibration registry. Passing this local target
check does not qualify the conditional exterior state or the physical model.
"""
import argparse,json,math
from pathlib import Path
from common_v3 import save,sha,verify
from select_selected_target_probe import choose


def plan(records,target=400,limit_ppm=1000):
    if len(records)<2 or not math.isfinite(target) or target<=0 or not math.isfinite(limit_ppm) or limit_ppm<0:raise ValueError('measured bank and finite positive target required')
    points=sorted(records,key=lambda r:r['controls']['fine']);first=points[0]
    for r in points:
        if any(r[k]!=first[k] for k in ['retained_device_operating_point','exterior_bias_operating_point']) or r['controls']['coarse']!=first['controls']['coarse']:raise ValueError('one common operating point and coarse bank required')
        code=r['controls']['fine'];frequency=r['frequency']['frequency_mhz']
        if type(code) is not int or not 8<=code<=247 or not math.isfinite(frequency) or frequency<=0:raise ValueError('finite measured frequency and supported fine code required')
    if any(a['controls']['fine']==b['controls']['fine'] or a['frequency']['frequency_mhz']>=b['frequency']['frequency_mhz'] for a,b in zip(points,points[1:])):raise ValueError('distinct increasing measured bank required')
    nearest=min(points,key=lambda r:abs(r['frequency']['frequency_mhz']-target));error=1e6*(nearest['frequency']['frequency_mhz']/target-1)
    if abs(error)<=limit_ppm:return dict(action='retain_measured_conditional_target',measured_case=nearest['case'],measured_frequency_mhz=nearest['frequency']['frequency_mhz'],nominal_error_ppm=error,requested_probe=None,frequency_assigned=False)
    low=[r for r in points if r['frequency']['frequency_mhz']<target];high=[r for r in points if r['frequency']['frequency_mhz']>target]
    if not low or not high:raise ValueError('measured target bracket required; no extrapolation')
    a,b=low[-1],high[0]
    return dict(action='measure_requested_probe',nearest_measured_case=nearest['case'],nearest_nominal_error_ppm=error,endpoint_cases=[a['case'],b['case']],requested_probe=choose([a,b],target),frequency_assigned=False)


def run(guides,output):
    if output.exists():raise FileExistsError(output)
    r=json.loads(guides.read_text());verify(r['input_sha256'])
    if r.get('conditional_guidance_only') is not True or r.get('full_corner_calibration_qualified') is not False:raise ValueError('explicit conditional guide scope required')
    for record in r['records']:
        case=Path(record['case']);receipt=case/'assessment.json'
        if r['input_sha256'].get(str(receipt))!=sha(receipt):raise ValueError('completed measured-point provenance required')
        a=json.loads(receipt.read_text());verify(a['input_sha256']);verify(a['artifacts'])
        if a.get('native_exit_zero') is not True or a['frequency']!=record['frequency'] or (a['coarse'],a['fine'])!=(record['controls']['coarse'],record['controls']['fine']):raise ValueError('point differs from actual completed native measurement')
    profile=Path(__file__).with_name('requirements_v3.json');p=json.loads(profile.read_text())
    files=[guides,profile,Path(__file__).resolve(),Path(__file__).with_name('select_selected_target_probe.py')]
    save(output,dict(input_sha256={str(f):sha(f) for f in files},selection=plan(r['records'],p['target_mhz'],p['frequency_error_ppm']),calibration_registry_modified=False,conditional_guidance_only=True,full_corner_calibration_qualified=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--guides',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run(a.guides.resolve(),a.output.resolve())
