"""Compare initial selected-bench voltages to the full native reference."""
import argparse,json,sys
from pathlib import Path
from common_v3 import ROOT,save,sha
sys.path.insert(0,str(ROOT))
from tools.xyce_umfpack.compare_prefix import Prefix


def compare(reference,candidate,tolerance=1e-6):
    r=Prefix(reference);c=Prefix(candidate)
    try:
        rv=r.sample(0);cv=c.sample(0)
        if rv[0]!=0 or cv[0]!=0:raise ValueError('DC sample must be at time zero')
        expected=dict(zip(r.names,rv));differences={}
        for name,value in zip(c.names[1:],cv[1:]):
            if name not in expected:raise ValueError('candidate output missing in native reference: '+name)
            differences[name]=abs(value-expected[name])
        if not differences:raise ValueError('no DC outputs captured')
        return dict(DC_output_comparison_pass=max(differences.values())<=tolerance,maximum_absolute_difference_V=max(differences.values()),differences_V=differences,tolerance_V=tolerance,transient_correlation_qualified=False,boundary_assumptions_validated=False,release_ready=False)
    finally:r.stream.close();c.stream.close()

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for key in ['reference','candidate','output']:p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args()
    if a.output.exists():p.error('fresh output required')
    result=compare(a.reference,a.candidate);result['input_sha256']={str(x.resolve()):sha(x) for x in [a.reference,a.candidate,Path(__file__)]};save(a.output,result);print(json.dumps(result))
