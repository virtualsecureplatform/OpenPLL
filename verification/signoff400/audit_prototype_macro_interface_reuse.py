"""Compare LEF pin geometry before considering reuse of an existing parent route."""
import argparse,json,re
from fractions import Fraction as F
from pathlib import Path
from common_v3 import save,sha,verify


def normalize(tokens):
    return [str(F(t)) if re.fullmatch(r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?',t) else t for t in tokens]


def interface(text):
    pins={};current=None;body=[];size=None;origin=None;master=None
    for line in text.splitlines():
        f=line.split()
        if not f:continue
        if current is not None:
            if f==['END',current]:
                if current in pins:raise ValueError('duplicate macro pin')
                pins[current]=normalize(body);current=None;body=[]
            else:body.extend(f)
            continue
        if f[0]=='MACRO':
            if master is not None:raise ValueError('one macro per LEF required')
            master=f[1]
        elif f[0]=='SIZE':
            if size is not None or len(f)!=5 or f[2]!='BY' or f[4]!=';':raise ValueError('unique explicit macro size required')
            size=normalize([f[1],f[3]])
        elif f[0]=='ORIGIN':origin=normalize(f[1:3])
        elif f[0]=='PIN':
            if len(f)!=2:raise ValueError('scalar LEF pin declaration required')
            current=f[1]
    if current is not None or not master or not size or not pins:raise ValueError('incomplete LEF interface')
    return dict(master=master,size_um=size,origin_um=origin,pins=pins)


def run(old,new,output):
    a,b=[interface(p.read_text()) for p in (old,new)]
    missing=sorted(a['pins'].keys()-b['pins'].keys());extra=sorted(b['pins'].keys()-a['pins'].keys())
    changed=sorted(name for name in a['pins'].keys()&b['pins'].keys() if a['pins'][name]!=b['pins'][name])
    matched=a['master']==b['master'] and a['size_um']==b['size_um'] and a['origin_um']==b['origin_um'] and not(missing or extra or changed)
    pins={str(p):sha(p) for p in (old,new,Path(__file__).resolve())};verify(pins)
    output.mkdir(parents=True,exist_ok=False);detail=output/'interfaces.json';save(detail,dict(original=a,candidate=b))
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},
        same_master=a['master']==b['master'],same_size=a['size_um']==b['size_um'],same_origin=a['origin_um']==b['origin_um'],
        original_pins=len(a['pins']),candidate_pins=len(b['pins']),missing_pins=missing,new_pins=extra,changed_pin_geometry_or_attributes=changed,
        exact_LEF_interface_match=matched,parent_route_geometry_reuse_qualified=False,
        new_parent_DRC_LVS_antenna_and_density_checks_required=True,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('old','new','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.old.resolve(),a.new.resolve(),a.output.resolve())
