"""Request recorded native clocks for the bound next synchronizer stage."""
import argparse,json
from pathlib import Path
from common_v3 import save,sha,verify


def run(base,continuation,output):
    if output.exists():raise FileExistsError(output)
    b,c=[json.loads(p.read_text()) for p in [base,continuation]]
    verify(b['input_sha256']);verify(c['input_sha256'])
    shared=set(b['input_sha256'])&set(c['input_sha256'])
    if len(shared)<3 or any(b['input_sha256'][p]!=c['input_sha256'][p] for p in shared):raise ValueError('same physical candidate required')
    endpoints=[e for row in c['records'] for e in row['continuation']['sequential_endpoints']]
    if len(endpoints)!=2 or any(e['input_pin']!='D' for e in endpoints):raise ValueError('two direct data endpoints required')
    clocks={e['cell']['pins']['CLK'] for e in endpoints}
    if len(clocks)!=1:raise ValueError('one next-stage clock required')
    roles=dict(b['clock_drivers']);roles['second_synchronizer_clock']=dict(node=next(iter(clocks)),kind='recorded_physical_interface_voltage')
    pins=dict(b['input_sha256']);pins.update(c['input_sha256']);pins.update({str(p):sha(p) for p in [base,continuation,Path(__file__).resolve()]});verify(pins)
    save(output,dict(input_sha256=pins,clock_drivers=roles,feedback_driver=b['feedback_driver'],driver_waveforms_qualified=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['base','continuation','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['base','continuation','output']))
