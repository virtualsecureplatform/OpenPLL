"""Replace selected signal guides and remove only their detailed wires.

Native OpenROAD Python; config comes from OPENPLL_SELECTED_GUIDE_CONFIG.
No cells, connections, power wires or nonselected guides are changed.
"""
import json
import os
from pathlib import Path
from common_v3 import save, sha, verify
from prototype_local_guide_regions import parse_guides, dump_guides, snap_box, replace_local_guides


def tree_edges(boxes):
    """Deterministic Manhattan minimum spanning tree of terminal box centers."""
    centers = [((b[0]+b[2])/2, (b[1]+b[3])/2) for b in boxes]
    reached = {0}; edges = []
    while len(reached) < len(boxes):
        _, a, b = min((abs(centers[a][0]-centers[b][0])+abs(centers[a][1]-centers[b][1]), a, b)
                      for a in sorted(reached) for b in range(len(boxes)) if b not in reached)
        reached.add(b); edges.append((a, b))
    return edges


def run(config_path):
    import odb
    config = json.loads(config_path.read_text()); source = Path(config['source']).resolve()
    output = Path(config['output']).resolve(); names = sorted(config['nets'])
    if not names or len(set(names)) != len(names):raise ValueError('unique nonempty net selection required')
    rr=source/'assessment.json';r=json.loads(rr.read_text());verify(r['input_sha256']);verify(r['artifacts'])
    db=source/'route.odb';guide=source/'global.guide';definition=source/'route.def'
    # This repair uses the measured regular prototype grid; reject other grids.
    import re
    text=definition.read_text();grids={}
    if re.findall(r'^UNITS DISTANCE MICRONS (\d+) ;',text,re.M)!=['1000']:raise ValueError('nanometer DB units required')
    for axis in ('X','Y'):
        matches=re.findall(r'^GCELLGRID '+axis+r' (-?\d+) DO (\d+) STEP (\d+) ;',text,re.M)
        if len(matches)!=1:raise ValueError('one regular guide grid per axis required')
        origin,count,pitch=map(int,matches[0]);grids[axis]=(origin,pitch)
        if count<2 or pitch<=0:raise ValueError('valid native guide grid required')
    origins=(grids['X'][0],grids['Y'][0]);pitches=(grids['X'][1],grids['Y'][1])
    original=parse_guides(guide.read_text());shapes=[s for group in original.values() for s in group]
    bounds=(min(s[0] for s in shapes),min(s[1] for s in shapes),max(s[2] for s in shapes),max(s[3] for s in shapes))
    D=odb.dbDatabase.create();odb.read_db(D,str(db));block=D.getChip().getBlock()
    site=D.findMaster('sky130_fd_sc_hs__fill_1').getWidth()
    def box(b):return (b.xMin(),b.yMin(),b.xMax(),b.yMax())
    def instances():return {i.getName():(i.getMaster().getName(),box(i.getBBox()),str(i.getOrient())) for i in block.getInsts()}
    before=instances();retained={n.getName():n.getWire().getId() for n in block.getNets() if n.getWire() and n.getName() not in names}
    replacements={};details=[]
    for name in names:
        net=block.findNet(name)
        if net is None or name not in original or str(net.getSigType()) in ('POWER','GROUND') or net.getWire() is None:
            raise ValueError('existing routed signal guide required: '+name)
        boxes=[];terminals=[]
        for term in sorted(net.getITerms(),key=lambda t:(t.getInst().getName(),t.getMTerm().getName())):
            b=box(term.getInst().getBBox());boxes.append(b)
            terminals.append(dict(cell=term.getInst().getName(),pin=term.getMTerm().getName(),bbox_nm=b))
        for term in sorted(net.getBTerms(),key=lambda t:t.getName()):
            bs=[box(b) for pin in term.getBPins() for b in pin.getBoxes()]
            if not bs:raise ValueError('placed signal port required')
            b=(min(b[0] for b in bs),min(b[1] for b in bs),max(b[2] for b in bs),max(b[3] for b in bs))
            boxes.append(b);terminals.append(dict(port=term.getName(),bbox_nm=b))
        if len(boxes)<2:raise ValueError('at least two native terminals required')
        regions=[]
        for b in boxes:
            for layer in ('li1','met1','met2'):
                shape=(*snap_box(b,site,origins,pitches,bounds),layer)
                if shape not in regions:regions.append(shape)
        edges=tree_edges(boxes)
        for a,b in edges:
            ba,bb=boxes[a],boxes[b]
            union=(min(ba[0],bb[0]),min(ba[1],bb[1]),max(ba[2],bb[2]),max(ba[3],bb[3]))
            corridor=snap_box(union,0,origins,pitches,bounds)
            for layer in ('met3','met4'):
                shape=(*corridor,layer)
                if shape not in regions:regions.append(shape)
        replacements[name]=regions;details.append(dict(net=name,terminals=terminals,tree_edges=edges,guide_regions=regions))
        odb.dbWire.destroy(net.getWire())
    if instances()!=before:raise ValueError('guide preparation changed an instance')
    if retained!={n.getName():n.getWire().getId() for n in block.getNets() if n.getWire() and n.getName() not in names}:
        raise ValueError('nonselected native wires changed')
    changed=replace_local_guides(original,replacements)
    inputs={str(p):sha(p) for p in (rr,db,guide,definition,config_path,Path(__file__).resolve(),Path(__file__).with_name('prototype_local_guide_regions.py'))}
    verify(inputs);output.mkdir(parents=True,exist_ok=False)
    (output/'routing.guide').write_text(dump_guides(changed));save(output/'corridors.json',details)
    checkpoint=output/'local_unrouted.odb';odb.write_db(D,str(checkpoint))
    save(output/'assessment.json',dict(input_sha256=inputs,
         artifacts={str(output/n):sha(output/n) for n in ('routing.guide','corridors.json','local_unrouted.odb')},
         source_database=str(db),checkpoint_database=str(checkpoint),selected_nets=names,
         local_corridors=len(names),native_guide_nets=len(original),
         unchanged_nonlocal_guide_nets=len(original)-len(names),nonlocal_guide_geometry_preserved=True,
         all_instances_and_nonselected_wires_unchanged=True,retained_signal_wires=len(retained),
         logical_connections_not_modified=True,native_detailed_route_legality_and_extracted_timing_required=True,
         release_ready=False))
    print(json.dumps(dict(selected_nets=len(names),retained_wires=len(retained))))


if __name__=='__main__':run(Path(os.environ['OPENPLL_SELECTED_GUIDE_CONFIG']).resolve())
