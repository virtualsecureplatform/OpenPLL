#!/usr/bin/env python3
"""Map current digital cell terminals to exact final-assembly coordinates.

Use actual GDS instance transforms and LEF pin rectangles, checking each
placement against the current macro DEF. This prepares physical correlation
of extracted capacitance with timing loads; it does not qualify those loads.
"""
import argparse
from collections import Counter
from decimal import Decimal
import json
import math
from pathlib import Path
import re
import signal
import sys
import time
import pya
from check_bbpd_repair_identity import design,section
from check_compact_clock_tree import verify
from check_compact_mapping import LEF
from run_dco_qualification import ROOT,sha,save


def lef_masters(path):
    result={}
    for name,body in re.findall(r'^MACRO (\S+)\s*\n(.*?)^END \1\s*$',path.read_text(),re.M|re.S):
        size=re.search(r'\bSIZE (\S+) BY (\S+)\s*;',body);assert size,name
        width,height=[int(Decimal(v)*1000) for v in size.groups()];pins={}
        for pin,pbody in re.findall(r'^\s*PIN (\S+)\s*$(.*?)^\s*END \1\s*$',body,re.M|re.S):
            use=re.search(r'\bUSE (\S+)\s*;',pbody);direction=re.search(r'\bDIRECTION (\S+)\s*;',pbody)
            rectangles=[];layer=None
            for line in pbody.splitlines():
                fields=line.split()
                if fields and fields[0]=='LAYER':layer=fields[1]
                if fields and fields[0]=='RECT':
                    nums=[Decimal(v)*1000 for v in fields[1:5]];assert all(int(v)==v for v in nums)
                    rectangles.append(dict(layer=layer,rect_nm=[int(v) for v in nums]))
            pins[pin]=dict(use=use[1] if use else 'SIGNAL',direction=direction[1] if direction else None,rectangles=rectangles)
        result[name]=dict(width=width,height=height,pins=pins)
    return result


def placed(body):
    match=re.search(r'\+ (?:PLACED|FIXED) \( (\d+) (\d+) \) (\S+)',body);assert match,body
    x,y,orient=match.groups();return int(x),int(y),orient


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();base=ROOT/'build/timing400/release_001';core=base/'compact_internal_antenna_001'
    final=base/'parent_dco_antenna_final_geometry_011/assessment.json';f=verify(final);assert f['geometry_checks_passed']
    verify(base/'compact_internal_antenna_closure_audit_001/assessment.json')
    route=base/'parent_dco_antenna_targeted_011/route.def';cells,parent_bindings,_=design(route)
    assert placed(cells['digital'][1])==(150000,150000,'N') or placed(cells['digital'][1])==(150000,150000,'R0')
    defpath=core/'route.def';components,bindings,nets=design(defpath)
    public={}
    for port,body in re.findall(r'^\s*-\s+(\S+)\s+(.*?);',section(defpath,'PINS'),re.M|re.S):
        net=re.search(r'\+ NET (\S+)',body);assert net,port
        parent=parent_bindings['digital',port]
        assert net[1] not in public or public[net[1]]==parent
        public[net[1]]=parent
    masters=lef_masters(LEF);gds=core/'signoff/route.gds'
    signoff=json.loads((core/'signoff/assessment.json').read_text());assert sha(gds)==signoff['sha256'][str(gds)]
    owner_path=base/'candidate_layout_checks_001/owner.json';deadline=json.loads(owner_path.read_text())['deadline_uptime']
    left=deadline-time.clock_gettime(time.CLOCK_BOOTTIME);assert left>0;signal.alarm(max(1,math.floor(left)))
    paths=[Path(__file__).resolve(),Path(sys.executable),Path(LEF),final,route,defpath,gds,
        core/'signoff/assessment.json',base/'compact_internal_antenna_closure_audit_001/assessment.json',owner_path]
    pins={str(p):sha(p) for p in paths}
    layout=pya.Layout();layout.read(str(gds));assert layout.dbu==.001
    top=layout.cell('IntegerPLL_AcquiringCore');assert top is not None
    placements={}
    for inst in top.each_inst():
        master=inst.cell.name
        if master not in masters:continue
        assert inst.na<=1 and inst.nb<=1
        info=masters[master];tr=inst.cplx_trans;assert tr.mag==1
        box=tr*pya.Box(0,0,info['width'],info['height'])
        key=(master,box.left,box.bottom);assert key not in placements,key
        placements[key]=tr
    rows=[];orientation_counts=Counter();missing=[];functional=0
    for instance,(master,body) in components.items():
        x,y,orient=placed(body);key=(master,x,y);assert key in placements,key
        tr=placements[key];orientation_counts[orient]+=1
        actual_orient=(int(round(tr.angle))%360,bool(tr.is_mirror()))
        allowed={'N':(0,False),'R0':(0,False),'FS':(0,True),'MX':(0,True),'S':(180,False),'R180':(180,False),'FN':(180,True),'MY':(180,True)}
        assert orient in allowed and actual_orient==allowed[orient],(instance,orient,actual_orient)
        functional_pins={name:p for name,p in masters[master]['pins'].items() if p['use'] not in ['POWER','GROUND']}
        if functional_pins:functional+=1
        for pin,info in functional_pins.items():
            net=bindings.get((instance,pin));points=[]
            for rect in info['rectangles']:
                layer=rect['layer'];kind='li' if layer=='li1' else ('m'+layer[-1] if re.fullmatch(r'met[1-5]',layer or '') else None)
                if kind is None:continue
                box=tr*pya.Box(*rect['rect_nm']);cx=(box.left+box.right)//2;cy=(box.bottom+box.top)//2
                assert box.left<cx<box.right and box.bottom<cy<box.top
                points.append(dict(layer=kind,point_nm=[cx+150000,cy+150000],rect_nm=[box.left+150000,box.bottom+150000,box.right+150000,box.top+150000]))
            assert points,(instance,pin)
            if net is None:missing.append(dict(instance=instance,master=master,pin=pin,direction=info['direction']))
            rows.append(dict(instance=instance,master=master,pin=pin,direction=info['direction'],macro_net=net,
                logical_net=public.get(net,'digital/'+net) if net is not None else None,probes=points))
    assert len(placements)==len(components),(len(placements),len(components))
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False);save(out/'terminals.json',rows)
    for path,d in pins.items():assert sha(path)==d,path
    save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(out/'terminals.json'):sha(out/'terminals.json')},
        components=len(components),matched_gds_placements=len(placements),orientation_counts=dict(orientation_counts),
        cells_with_signal_pins=functional,signal_terminals=len(rows),physical_rectangular_probes=sum(len(r['probes']) for r in rows),
        distinct_connected_logical_nets=len({r['logical_net'] for r in rows if r['logical_net'] is not None}),
        unconnected_terminals=missing,exact_def_gds_instance_transforms=True,macro_global_offset_nm=[150000,150000],
        gds_connectivity_correlation_pending=True,effective_load_enclosure_qualified=False,physical_timing_qualified=False,
        release_qualified=False,adopted=False,scope=__doc__))
    print('Mapped',len(rows),'signal terminals in',functional,'cells using',len(placements),'exact GDS/DEF placements.')

if __name__=='__main__':main()
