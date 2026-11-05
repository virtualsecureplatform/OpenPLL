"""Prepare local corridor hints; native detailed routing must prove legality.

Run with OpenROAD Python and OPENPLL_DIRECT_GUIDE_CONFIG. No routed geometry
or logical connections are edited by this preparation step.
"""
import json
import os
from pathlib import Path
import re
from common_v3 import save,sha,verify
from prototype_local_guide_regions import parse_guides,dump_guides,snap_box,replace_local_guides


def run(config):
    import odb
    source=Path(config['source']).resolve();plan=Path(config['plan']).resolve()
    output=Path(config['output']).resolve();namespace=config['namespace']
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*',namespace):raise ValueError('safe ECO namespace required')
    rr=source/'assessment.json';r=json.loads(rr.read_text());p=json.loads(plan.read_text())
    verify(r['input_sha256']);verify(r['artifacts']);verify(p['input_sha256'])
    if r['input_sha256'].get(str(plan))!=sha(plan) or p['targets'] or p['branches'] or p.get('short_data_targets'):
        raise ValueError('same-source buffer/pair-only checkpoint required')
    db=source/'antenna_repaired.odb';guide=source/'global.guide';definition=source/'route.def'
    text=definition.read_text();grids={}
    if re.findall(r'^UNITS DISTANCE MICRONS (\d+) ;',text,re.M)!=['1000']:raise ValueError('prototype DB units must be nanometers')
    for axis in ('X','Y'):
        matches=re.findall(r'^GCELLGRID '+axis+r' (-?\d+) DO (\d+) STEP (\d+) ;',text,re.M)
        if len(matches)!=1:raise ValueError('one regular native grid per axis required')
        origin,count,pitch=map(int,matches[0]);grids[axis]=(origin,pitch)
        if count<2 or pitch<=0:raise ValueError('invalid native guide grid')
    original=parse_guides(guide.read_text())
    all_shapes=[s for shapes in original.values() for s in shapes]
    bounds=(min(s[0] for s in all_shapes),min(s[1] for s in all_shapes),
            max(s[2] for s in all_shapes),max(s[3] for s in all_shapes))
    origins=(grids['X'][0],grids['Y'][0]);pitches=(grids['X'][1],grids['Y'][1])
    names=[f'{namespace}_source_{i}_net' for i in range(len(p.get('source_buffers',[])))]
    names += [f'{namespace}_pair_{i}_{s}_net' for i in range(len(p.get('source_inverter_pairs',[]))) for s in (0,1)]
    D=odb.dbDatabase.create();odb.read_db(D,str(db));block=D.getChip().getBlock()
    site=D.findMaster('sky130_fd_sc_hs__fill_1').getWidth();replacements={};details=[]
    for name in names:
        net=block.findNet(name)
        if net is None or str(net.getSigType()) in ('POWER','GROUND') or list(net.getBTerms()):
            raise ValueError('local internal signal net required')
        terms=list(net.getITerms())
        if len(terms)!=2:raise ValueError('two-terminal local net required')
        boxes=[];pins=[]
        for term in terms:
            inst=term.getInst();b=inst.getBBox();box=(b.xMin(),b.yMin(),b.xMax(),b.yMax())
            boxes.append(box);pins.append(dict(cell=inst.getName(),pin=term.getMTerm().getName(),bbox_nm=box))
        union=(min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes))
        corridor=snap_box(union,max(pitches),origins,pitches,bounds)
        pin_regions=[snap_box(b,site,origins,pitches,bounds) for b in boxes]
        shapes=[]
        for box in pin_regions:
            for layer in ('li1','met1','met2'):
                shape=(*box,layer)
                if shape not in shapes:shapes.append(shape)
        shapes.extend((*corridor,layer) for layer in ('met3','met4'))
        replacements[name]=shapes;details.append(dict(net=name,terminals=pins,guide_regions=shapes))
    changed=replace_local_guides(original,replacements)
    files=(rr,plan,db,guide,definition,Path(__file__).resolve(),Path(config['config_path']),
           Path(__file__).with_name('prototype_local_guide_regions.py'))
    inputs={str(f):sha(f) for f in files};verify(inputs);output.mkdir(parents=True,exist_ok=False)
    target=output/'routing.guide';target.write_text(dump_guides(changed));detail=output/'corridors.json';save(detail,details)
    save(output/'assessment.json',dict(input_sha256=inputs,artifacts={str(f):sha(f) for f in (target,detail)},
         local_corridors=len(replacements),native_guide_nets=len(original),
         unchanged_nonlocal_guide_nets=len(original)-len(replacements),
         nonlocal_guide_geometry_preserved=True,logical_connections_and_routed_wires_not_modified=True,
         native_detailed_route_legality_and_extracted_timing_required=True,release_ready=False))
    print(json.dumps(dict(local_corridors=len(replacements),unchanged_guides=len(original)-len(replacements))))


if __name__=='__main__':
    path=Path(os.environ['OPENPLL_DIRECT_GUIDE_CONFIG']).resolve();config=json.loads(path.read_text())
    config['config_path']=str(path);run(config)
