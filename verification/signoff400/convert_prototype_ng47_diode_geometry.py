"""Convert extracted diode geometry to ngspice47 effective instance units; leave MOS/C untouched."""
import argparse
from collections import Counter
from fractions import Fraction as F
import json
from pathlib import Path
from common_v3 import save,sha,verify
from build_prototype_DCO_rc import decimal
from compare_prototype_analog_devices_v2 import devices
from prepare_prototype_analog_reference import subcircuits

MODEL='sky130_fd_pr__diode_pw2nd_05v5'
KNOWN={(F('0.4347'),F('2.64')),(F('0.6417'),F('3.24'))}


def convert(text):
    lines=[];changes=[]
    for line in text.splitlines():
        f=line.split()
        if not f or f[0].startswith('*') or MODEL not in f:lines.append(line);continue
        if len(f)!=6 or not f[0].lower().startswith('x') or f[3]!=MODEL:raise ValueError('unreviewed diode card syntax')
        params=dict(t.split('=',1) for t in f[4:])
        if len(params)!=2 or set(params)!={'area','perim'}:raise ValueError('explicit diode area/perimeter required')
        a,p=F(params['area'])/10**12,F(params['perim'])/10**6
        if (a,p) not in KNOWN:raise ValueError('diode geometry outside independently reviewed HD/HS masters')
        new=' '.join(f[:4]+['area='+decimal(a),'perim='+decimal(p)])
        changes.append(dict(instance=f[0],original=line,converted=new,physical_area_um2=str(a),physical_perimeter_um=str(p)))
        lines.append(new)
    if not changes:raise ValueError('no supported diode instances')
    return '\n'.join(lines)+'\n',changes


def check(original,converted,top):
    a=devices(subcircuits(original),top);b=devices(subcircuits(converted),top);expected=Counter()
    for (model,nodes,parameters),count in a.items():
        params=dict(parameters)
        if model==MODEL:
            params['area']=str(F(params['area'])/10**12);params['perim']=str(F(params['perim'])/10**6)
        expected[(model,nodes,tuple(sorted(params.items())))]+=count
    if expected!=b:raise ValueError('conversion changed non-diode cards or failed exact unit mapping')
    return dict(expanded_primitive_instances=sum(a.values()),expanded_diodes=sum(n for (m,_,_),n in a.items() if m==MODEL),
        exact_expanded_conversion_reparse_pass=True)


def run(source,top,output):
    output.mkdir(parents=True,exist_ok=False)
    pins={str(p):sha(p) for p in (source,Path(__file__).resolve(),Path(__file__).with_name('build_prototype_DCO_rc.py'),Path(__file__).with_name('compare_prototype_analog_devices_v2.py'),Path(__file__).with_name('prepare_prototype_analog_reference.py'))}
    original=source.read_text();converted,changes=convert(original);proof=check(original,converted,top)
    model=output/'ng47.spice';model.write_text(converted);detail=output/'conversion.json';save(detail,dict(changes=changes,proof=proof));verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(model):sha(model),str(detail):sha(detail)},**proof,
        original_extraction_units_preserved_in_archive=True,ng47_effective_diode_geometry_applied=True,
        native_electrical_control_complete=False,diagnostic=True,validated_for_prototype=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True);p.add_argument('--top',required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run(a.source.resolve(),a.top,a.output.resolve())
