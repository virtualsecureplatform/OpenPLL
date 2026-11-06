"""Choose an unmeasured fine code inside a measured conditional target bracket."""
import argparse,json,math
from fractions import Fraction
from pathlib import Path
from common_v3 import save,sha,verify


def choose(records,target=400):
    if len(records)!=2:raise ValueError('exactly two measured endpoints required')
    a,b=sorted(records,key=lambda r:r['controls']['fine'])
    keys=['retained_device_operating_point','exterior_bias_operating_point']
    if any(a[k]!=b[k] for k in keys) or a['controls']['coarse']!=b['controls']['coarse']:raise ValueError('same operating point and coarse bank required')
    x,y=[r['controls']['fine'] for r in [a,b]];f,g=[r['frequency']['frequency_mhz'] for r in [a,b]]
    if any(type(v) is not int or not 8<=v<=247 for v in [x,y]) or x==y:raise ValueError('distinct supported measured fine codes required')
    if any(not math.isfinite(v) or v<=0 for v in [f,g,target]) or not f<target<g:raise ValueError('positive-slope measured target bracket required')
    estimate=Fraction(x)+(Fraction(str(target))-Fraction(str(f)))*(y-x)/(Fraction(str(g))-Fraction(str(f)))
    fine=(estimate.numerator*2+estimate.denominator)//(estimate.denominator*2)
    if not x<fine<y:raise ValueError('no unmeasured interior integer code selected')
    return dict(coarse=a['controls']['coarse'],fine=fine,corner=a['retained_device_operating_point']['corner'],target_mhz=target,frequency_assigned=False,reason='nearest integer to two-endpoint interpolation; native measurement still required')


def run(bracket,output):
    if output.exists():raise FileExistsError(output)
    r=json.loads(bracket.read_text());verify(r['input_sha256'])
    if not r.get('conditional_guidance_only') or r.get('full_corner_calibration_qualified') is not False:raise ValueError('explicit conditional guide scope required')
    for record in r['records']:
        case=Path(record['case']);assessment=case/'assessment.json'
        if r['input_sha256'].get(str(assessment))!=sha(assessment):raise ValueError('measured endpoint provenance required')
        a=json.loads(assessment.read_text());verify(a['input_sha256']);verify(a['artifacts'])
        if not a['native_exit_zero'] or a['frequency']!=record['frequency'] or (a['coarse'],a['fine'])!=(record['controls']['coarse'],record['controls']['fine']):raise ValueError('endpoint differs from completed native measurement')
    save(output,dict(input_sha256={str(bracket):sha(bracket),str(Path(__file__).resolve()):sha(Path(__file__).resolve())},requested_probe=choose(r['records']),calibration_registry_modified=False,full_corner_calibration_qualified=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bracket',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run(a.bracket.resolve(),a.output.resolve())
