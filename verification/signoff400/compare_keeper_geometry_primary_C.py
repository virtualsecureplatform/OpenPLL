"""Compare exact primary-port restrictions of three checked C representations."""
import argparse,json,os,time
from pathlib import Path
from collections import defaultdict
from fractions import Fraction as F
from common_v3 import save,sha,verify
from resources import lease
from compare_keeper_primary_C import groups,stamp,hierarchy_aliases
from build_prototype_full_C_wire_R_v11 import Union
from native_spice_comments import strip_floating_annotation
from audit_hierarchical_capacitance import number


def flat_matrix(path):
    aliases=Union();ports=[];continuation=False;tops=0;counts=dict(positive=0,negative=0,zero=0)
    for line in path.open():
        f=strip_floating_annotation(line).split()
        if not f:continue
        if f[0].lower()=='.subckt':
            tops+=1;ports=f[2:];continuation=True
        elif f[0]=='+':
            if not continuation:raise ValueError('unexpected continued device syntax')
            ports.extend(f[1:])
        else:continuation=False
        if f[0].startswith('R'):
            if len(f)!=4 or number(f[-1])!=0:raise ValueError('only explicit zero-R aliases supported')
            aliases.join(f[1],f[2])
    if tops!=1 or len(ports)!=len(set(ports)):raise ValueError('one flat top with unique ports required')
    mapping=groups(ports,aliases.find);matrix=defaultdict(F)
    for line in path.open():
        f=strip_floating_annotation(line).split()
        if f and f[0].startswith('C'):
            if len(f)!=4:raise ValueError('unreviewed C syntax')
            c=number(f[-1]);counts['positive'if c>0 else'negative'if c<0 else'zero']+=1
            stamp(matrix,aliases.find(f[1]),aliases.find(f[2]),c,mapping)
    return ports,mapping,{k:v for k,v in matrix.items()if v},counts


def differences(a,b):
    return [dict(row_ports=list(k[0]),column_ports=list(k[1]),left_F=str(a.get(k,F())),right_F=str(b.get(k,F())),right_minus_left_F=str(b.get(k,F())-a.get(k,F())))for k in sorted(a.keys()|b.keys())if a.get(k,F())!=b.get(k,F())]


def run(projected,native,flat,lvs,output):
    receipts=[p/'assessment.json'for p in [projected,native,flat,lvs]];h,n,f,l=[json.loads(p.read_text())for p in receipts]
    for r in [h,n,f,l]:verify(r['input_sha256']);verify(r['artifacts'])
    if not l['unique_device_LVS_match']or not l['all_records_without_discrepancies']or l['input_sha256'].get(str(receipts[2]))!=sha(receipts[2]):raise ValueError('matching geometry device LVS required')
    sources=[Path(p)for p in h['input_sha256']if p.endswith('/capacitance.spice')];exports=[Path(p)for p in n['artifacts']if p.endswith('/signed_threshold.spice')]
    if len(sources)!=1 or len(exports)!=1:raise ValueError('one checked hierarchical and native export source required')
    raw=flat/'capacitance.spice';pairs=projected/'dynamic.pairs.jsonl'
    if f['artifacts'].get(str(raw))!=sha(raw):raise ValueError('geometry C source missing from receipt')
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{24});folder=Path(__file__).resolve().parent
    files=[*receipts,*sources,*exports,raw,pairs,Path(__file__).resolve(),*[folder/name for name in ['compare_keeper_primary_C.py','build_prototype_full_C_wire_R_v11.py','native_spice_comments.py','audit_hierarchical_capacitance.py']]];pins={str(p):sha(p)for p in files}
    with lease(1,8,time.clock_gettime(time.CLOCK_BOOTTIME)+600):
        hp,canonical=hierarchy_aliases(sources[0].read_text(),sources[0].parent.name);hg=groups(hp,canonical);hm=defaultdict(F)
        for line in pairs.open():
            r=json.loads(line);stamp(hm,*r['nodes'],F(r['farads']),hg)
        hm={k:v for k,v in hm.items()if v};np,ng,nm,nc=flat_matrix(exports[0]);fp,fg,fm,fc=flat_matrix(raw)
        if hp!=np or hp!=fp:raise ValueError('ordered primary ports differ')
        if set(hg.values())!=set(ng.values())or set(hg.values())!=set(fg.values()):raise ValueError('primary zero-R alias partitions differ')
    artifacts={};summary={}
    for name,left,right in [('hierarchy_vs_native_export',hm,nm),('hierarchy_vs_flat_geometry',hm,fm),('native_export_vs_flat_geometry',nm,fm)]:
        detail=differences(left,right);path=output/(name+'.json');save(path,detail);artifacts[str(path)]=sha(path);summary[name]=dict(differing_matrix_entries=len(detail),exactly_equal=not detail)
    diagonals=[]
    for port in sorted(set(hg.values())):
        k=(port,port);diagonals.append(dict(ports=list(port),hierarchy_F=str(hm.get(k,F())),native_export_F=str(nm.get(k,F())),flat_geometry_F=str(fm.get(k,F()))))
    detail=output/'diagonals.json';save(detail,diagonals);artifacts[str(detail)]=sha(detail);verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,comparisons=summary,primary_ports=len(hp),non_supply_alias_groups=len(hg),ordered_ports_and_alias_groups_equal=True,native_export_capacitor_counts=nc,flat_geometry_capacitor_counts=fc,all_other_conductor_voltages_fixed=True,intrinsic_device_C_included=False,physical_error_bound_claimed=False,models_modified=False,model_qualified=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ['projected','native','flat','lvs','output']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve()for n in ['projected','native','flat','lvs','output']))
