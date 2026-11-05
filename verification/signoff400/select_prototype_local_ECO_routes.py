"""Clear signal routes near actual cell changes, preserving all other wires.

Run with OpenROAD's embedded Python and OPENPLL_LOCAL_ECO_CONFIG. Unsupported
wire encodings conservatively force that net into the rerouting set.
"""
import json
import os
from pathlib import Path
import re
from common_v3 import save,sha,verify


def route_records(text):
    section=re.search(r'^NETS \d+ ;\n(.*?)^END NETS',text,re.M|re.S)
    if section is None:raise ValueError('DEF signal NETS section required')
    routes={}
    for block in re.split(r'(?m)^[ \t]*- ',section[1])[1:]:
        name=block.split()[0]
        if name in routes:raise ValueError('duplicate DEF net')
        start=re.search(r'\+ (?:ROUTED|FIXED|COVER)\b',block)
        if start:routes[name]=' '.join(block[start.start():].split())
    if not routes:raise ValueError('nonempty routed DEF required')
    return routes


def spacer(master):
    return master in {f'sky130_fd_sc_hs__fill_{n}' for n in (1,2,4,8)}


def overlaps(a,b):
    return a[0]<=b[2] and b[0]<=a[2] and a[1]<=b[3] and b[1]<=a[3]


def change_windows(before,after,margin):
    windows=[];changed=[]
    for name,old in before.items():
        if spacer(old['master']):continue
        if name not in after:raise ValueError('non-spacer instance removed: '+name)
    for name,new in after.items():
        if spacer(new['master']):continue
        old=before.get(name)
        if old==new:continue
        changed.append(name)
        for row in (old,new) if old else (new,):
            x1,y1,x2,y2=row['bbox'];windows.append((x1-margin,y1-margin,x2+margin,y2+margin))
    return changed,windows


def tcl_literal(value):
    if any(c in value for c in '{}\r\n') or value.endswith('\\'):
        raise ValueError('unsupported Tcl net name')
    return '{'+value+'}'


def bbox(obj):
    return (obj.xMin(),obj.yMin(),obj.xMax(),obj.yMax())


def poses(block):
    return {i.getName():dict(master=i.getMaster().getName(),bbox=list(bbox(i.getBBox())),orient=str(i.getOrient()))
            for i in block.getInsts()}


def wire_rectangles(wire,odb):
    dec=odb.dbWireDecoder();dec.begin(wire);point=None;known={};rects=[]
    while True:
        op=dec.next()
        if op==dec.END_DECODE:return rects
        if op==dec.PATH:point=None
        elif op in (dec.POINT,dec.POINT_EXT):
            values=dec.getPoint() if op==dec.POINT else dec.getPoint_ext()
            current=tuple(values[:2])
            if point is not None:
                rects.append((min(point[0],current[0]),min(point[1],current[1]),
                              max(point[0],current[0]),max(point[1],current[1])))
            rects.append((*current,*current))
            if op==dec.POINT_EXT:
                extent=abs(values[2]);rects.append((current[0]-extent,current[1]-extent,current[0]+extent,current[1]+extent))
            known[dec.getJunctionId()]=current;point=current
        elif op in (dec.VIA,dec.TECH_VIA):
            if point is None:return None
            rects.append((*point,*point))
        elif op==dec.JUNCTION:
            point=known.get(dec.getJunctionValue())
            if point is None:return None
        elif op in (dec.ITERM,dec.BTERM):pass
        else:return None


def run(config):
    import odb
    source=Path(config['source']).resolve();checkpoint=Path(config['checkpoint']).resolve()
    output=Path(config['output']).resolve();margin_um=float(config.get('margin_um',2))
    if not 1<=margin_um<=5:raise ValueError('review locality margin outside 1–5um')
    rr=source/'assessment.json';cr=checkpoint/'assessment.json'
    r,c=[json.loads(f.read_text()) for f in (rr,cr)]
    for record in (r,c):verify(record['input_sha256']);verify(record['artifacts'])
    if c['input_sha256'].get(str(rr))!=sha(rr):raise ValueError('checkpoint source identity differs')
    definition=source/'route.def'
    units=re.findall(r'^UNITS DISTANCE MICRONS (\d+) ;',definition.read_text(),re.M)
    if units!=['1000']:raise ValueError('review database units before selecting local wires')
    before_db=odb.dbDatabase.create();odb.read_db(before_db,str(source/'route.odb'))
    after_db=odb.dbDatabase.create();odb.read_db(after_db,str(checkpoint/'pre_antenna.odb'))
    before=before_db.getChip().getBlock();after=after_db.getChip().getBlock()
    changed,windows=change_windows(poses(before),poses(after),round(margin_um*1000))
    if not changed:raise ValueError('nonempty actual ECO required')
    dirty=set();reasons={};fallback=0;retained=0
    for block in (before,after):
        for name in changed:
            inst=block.findInst(name)
            if inst is None:continue
            for term in inst.getITerms():
                net=term.getNet()
                if net is not None and str(net.getSigType()) not in ('POWER','GROUND'):
                    dirty.add(net.getName());reasons.setdefault(net.getName(),set()).add('changed_instance_terminal')
    for net in after.getNets():
        if str(net.getSigType()) in ('POWER','GROUND'):continue
        name=net.getName();wire=net.getWire()
        if wire is None:
            dirty.add(name);reasons.setdefault(name,set()).add('unrouted_signal');continue
        if name not in dirty:
            rectangles=wire_rectangles(wire,odb)
            if rectangles is None:
                # getBBox returns an unwrapped std::optional<Rect> in this
                # pinned Python binding. Unknown encodings must be rerouted.
                fallback+=1
                dirty.add(name);reasons.setdefault(name,set()).add('unsupported_wire_encoding')
            elif any(overlaps(rect,w) for rect in rectangles for w in windows):
                dirty.add(name);reasons.setdefault(name,set()).add('near_changed_instance')
        if name in dirty:odb.dbWire.destroy(wire)
        else:retained+=1
    output.mkdir(parents=True,exist_ok=False)
    script=output/'dirty_nets.tcl'
    script.write_text('set local_eco_dirty_nets [list '+' '.join(tcl_literal(n) for n in sorted(dirty))+']\n')
    odb.write_db(after_db,str(output/'local_unrouted.odb'))
    detail=output/'selection.json';save(detail,dict(changed_instances=changed,windows_nm=windows,
         dirty_nets={n:sorted(v) for n,v in sorted(reasons.items())}))
    inputs={str(f):sha(f) for f in (rr,cr,source/'route.odb',definition,checkpoint/'pre_antenna.odb',
                                  Path(__file__).resolve(),Path(config['config_path']))}
    save(output/'assessment.json',dict(input_sha256=inputs,
         artifacts={str(f):sha(f) for f in (script,detail,output/'local_unrouted.odb')},
         changed_instances=len(changed),dirty_signal_nets=len(dirty),retained_signal_wires=retained,
         unsupported_wire_encoding_fallbacks=fallback,locality_margin_um=margin_um,
         special_power_wires_not_modified=True,postroute_validation_required=True,
         physical_timing_qualified=False,release_ready=False))
    print(json.dumps(dict(changed_instances=len(changed),dirty_nets=len(dirty),retained_wires=retained)))


if __name__=='__main__':
    path=Path(os.environ['OPENPLL_LOCAL_ECO_CONFIG']).resolve();config=json.loads(path.read_text())
    config['config_path']=str(path);run(config)
