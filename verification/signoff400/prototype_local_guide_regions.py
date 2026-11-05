"""Read native routing guides and construct bounded local guide regions."""
import math


def parse_guides(text):
    lines=iter(text.splitlines());result={}
    for line in lines:
        name=line.strip()
        if not name:continue
        if name in result or next(lines).strip()!='(':raise ValueError('invalid guide record')
        shapes=[]
        for line in lines:
            if line.strip()==')':break
            fields=line.split()
            if len(fields)!=5:raise ValueError('five guide fields required')
            x1,y1,x2,y2=map(int,fields[:4])
            if x1>=x2 or y1>=y2:raise ValueError('positive guide region required')
            shapes.append((x1,y1,x2,y2,fields[4]))
        else:raise ValueError('unterminated guide record')
        if not shapes:raise ValueError('empty native guide record')
        result[name]=shapes
    if not result:raise ValueError('nonempty guide inventory required')
    return result


def dump_guides(guides):
    return ''.join(name+'\n(\n'+''.join(' '.join(map(str,s))+'\n' for s in shapes)+')\n'
                   for name,shapes in guides.items())


def snap_box(box,padding,origins,pitches,bounds):
    values=[]
    for coordinate,pad,origin,pitch,lower,upper,minimum in zip(
            box,(padding,)*4,origins*2,pitches*2,bounds[:2]+bounds[:2],bounds[2:]+bounds[2:],(True,True,False,False)):
        if pitch<=0 or padding<0:raise ValueError('positive guide grid required')
        value=coordinate-pad if minimum else coordinate+pad
        snapped=origin+(math.floor((value-origin)/pitch) if minimum else math.ceil((value-origin)/pitch))*pitch
        values.append(max(lower,min(upper,snapped)))
    if values[0]>=values[2] or values[1]>=values[3]:raise ValueError('clipped guide region is empty')
    return tuple(values)


def replace_local_guides(original,replacements):
    if not replacements or not replacements.keys()<=original.keys():raise ValueError('existing local guide names required')
    result={name:list(replacements.get(name,shapes)) for name,shapes in original.items()}
    if any(result[n]!=shapes for n,shapes in original.items() if n not in replacements):
        raise ValueError('nonlocal guide changed')
    return result
