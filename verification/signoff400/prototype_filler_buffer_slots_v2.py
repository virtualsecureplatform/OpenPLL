"""Allocate exact standard-cell filler footprints without moving existing logic."""
from collections import defaultdict

PREFIX='sky130_fd_sc_hs__fill_'


def filler(master):
    return master in {PREFIX+str(n) for n in (1,2,4,8)}


def partition(start,stop,site):
    if stop<start or (stop-start)%site:raise ValueError('unaligned filler interval')
    result=[]
    for size in (8,4,2,1):
        while stop-start>=size*site:
            result.append((start,PREFIX+str(size)));start+=size*site
    if start!=stop:raise ValueError('inexact filler partition')
    return result


def allocate(instances,requests,site=480,max_distance=20000):
    """Return sequential donor replacements; caller must replay in this order.

    A slot may span several adjacent filler instances. Each replaced rectangle
    is tiled exactly by the new buffer and leftover fillers. Logic is never a
    donor. Distance is from the buffer lower-left to the supplied cell anchor.
    """
    state={n:dict(v) for n,v in instances.items()};allocations=[]
    for index,request in enumerate(requests):
        name=request['name'];width=request['width'];height=request['height']
        if name in state or width<=0 or width%site:raise ValueError('fresh aligned buffer required')
        rows=defaultdict(list)
        for n,i in state.items():
            if not filler(i['master']):continue
            a,b,c,d=i['bbox']
            if i['orient'] not in ('R0','MX','MY','R180') or (c-a)%site:
                raise ValueError('unsupported filler geometry')
            if d-b==height:rows[(b,d,i['orient'])].append((a,c,n))
        best=None
        if 'anchor_instance' in request:
            anchor=state[request['anchor_instance']]['bbox'][:2]
        else:anchor=request['anchor']
        sx,sy=anchor
        for (bottom,top,orient),pieces in rows.items():
            runs=[]
            for a,c,n in sorted(pieces):
                if runs and a<runs[-1][-1][1]:raise ValueError('overlapping filler donors')
                if not runs or a!=runs[-1][-1][1]:runs.append([])
                runs[-1].append((a,c,n))
            for run in runs:
                left,right=run[0][0],run[-1][1]
                if right-left<width:continue
                offset=min(max(round((sx-left)/site),0),(right-left-width)//site)
                x=left+offset*site;distance=abs(x-sx)+abs(bottom-sy)
                donors=[p for p in run if p[0]<x+width and x<p[1]]
                key=(distance,len(donors),bottom,x,orient)
                if best is None or key<best[0]:best=(key,x,bottom,top,orient,donors)
        if best is None or best[0][0]>max_distance:
            raise ValueError('no contiguous filler slot within distance bound: '+name)
        key,x,bottom,top,orient,donors=best
        donor_boxes={n:dict(state[n]) for _,_,n in donors}
        left,right=donors[0][0],donors[-1][1]
        leftovers=partition(left,x,site)+partition(x+width,right,site)
        pieces=[]
        for j,(a,master) in enumerate(leftovers):
            count=int(master.rsplit('_',1)[1]);n=f'{name}_slot_fill_{j}'
            if n in state:raise ValueError('filler namespace collision')
            record=dict(master=master,bbox=[a,bottom,a+count*site,top],orient=orient)
            state[n]=record;pieces.append(dict(name=n,**record))
        for _,_,n in donors:del state[n]
        record=dict(master=request['master'],bbox=[x,bottom,x+width,top],orient=orient)
        state[name]=record
        tiling=sorted([p['bbox'] for p in pieces]+[record['bbox']])
        cursor=left
        for a,b,c,d in tiling:
            if a!=cursor or b!=bottom or d!=top:raise ValueError('donor footprint not preserved')
            cursor=c
        if cursor!=right:raise ValueError('donor footprint changed')
        allocations.append(dict(name=name,**record,donors=[n for _,_,n in donors],
                                donor_boxes=donor_boxes,
                                fillers=pieces,distance_dbu=key[0]))
    return allocations


def render(allocations):
    def word(name):
        if any(c in name for c in '{}\\\n\r'):raise ValueError('unsafe instance name')
        return '{'+name+'}'
    setup='''proc fixed_slot_place {inst orient xmin ymin width height} {
 $inst setOrient $orient
 $inst setLocation 0 0
 set box [$inst getBBox]
 $inst setLocation [expr {$xmin-[$box xMin]}] [expr {$ymin-[$box yMin]}]
 $inst setPlacementStatus PLACED
 set box [$inst getBBox]
 if {[list [$box xMin] [$box yMin] [$box xMax] [$box yMax]] ne [list $xmin $ymin [expr {$xmin+$width}] [expr {$ymin+$height}]]} {error "fixed slot footprint differs"}
}
'''
    placements=[]
    for entry in allocations:
        for n in entry['donors']:
            old=entry['donor_boxes'][n];coords=' '.join(map(str,old['bbox']))
            setup+=f'''set donor [$block findInst {word(n)}]
if {{$donor eq {{NULL}} || [[$donor getMaster] getName] ne {word(old['master'])} || [$donor getOrient] ne {word(old['orient'])}}} {{error "filler donor changed"}}
set box [$donor getBBox]
if {{[list [$box xMin] [$box yMin] [$box xMax] [$box yMax]] ne {{{coords}}}}} {{error "filler donor box changed"}}
odb::dbInst_destroy $donor
'''
        for piece in entry['fillers']:
            a,b,c,d=piece['bbox']
            setup+=f'''if {{[$block findInst {word(piece['name'])}] ne {{NULL}}}} {{error "fresh slot filler required"}}
set piece [odb::dbInst_create $block [[ord::get_db] findMaster {word(piece['master'])}] {word(piece['name'])}]
fixed_slot_place $piece {piece['orient']} {a} {b} {c-a} {d-b}
foreach pin {{VPWR VPB}} {{[$piece findITerm $pin] connect [$block findNet VDD]}}
foreach pin {{VGND VNB}} {{[$piece findITerm $pin] connect [$block findNet VSS]}}
'''
        a,b,c,d=entry['bbox']
        placements.append(f'''set piece [$block findInst {word(entry['name'])}]
if {{$piece eq {{NULL}} || [[$piece getMaster] getName] ne {word(entry['master'])}}} {{error "planned slot buffer differs"}}
fixed_slot_place $piece {entry['orient']} {a} {b} {c-a} {d-b}
puts "FIXED_BUFFER_SLOT name={entry['name']} distance_dbu={entry['distance_dbu']}"
''')
    return setup,'\n'.join(placements)
