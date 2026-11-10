"""Use the shared S/D edge, rather than the whole device tile, as breakpoint."""
def transform(text):
    if 'OPENPLL shared source/drain edge midpoint' in text:
        raise ValueError('unmodified source/drain edge calculations required')
    for edge,axis,before,after in [
        ('RIGHTEDGE','y','(TOP(tp) + BOTTOM(tp))','(MIN(TOP(tile), TOP(tp)) + MAX(BOTTOM(tile), BOTTOM(tp)))'),
        ('LEFTEDGE','y','(TOP(tp) + BOTTOM(tp))','(MIN(TOP(tile), TOP(tp)) + MAX(BOTTOM(tile), BOTTOM(tp)))'),
        ('BOTTOMEDGE','x','(LEFT(tp) + RIGHT(tp))','(MAX(LEFT(tile), LEFT(tp)) + MIN(RIGHT(tile), RIGHT(tp)))'),
        ('TOPEDGE','x','(LEFT(tp) + RIGHT(tp))','(MAX(LEFT(tile), LEFT(tp)) + MIN(RIGHT(tile), RIGHT(tp)))')]:
        original=f'{axis}j = {before} >> 1;\n\t\t\tResNewSDDevice(tile, tp, xj, yj, {edge}, &ResNodeQueue);'
        changed=f'/* OPENPLL shared source/drain edge midpoint. */\n\t\t\t{axis}j = {after} >> 1;\n\t\t\tResNewSDDevice(tile, tp, xj, yj, {edge}, &ResNodeQueue);'
        if text.count(original)!=1:raise ValueError('one pinned native '+edge+' source/drain midpoint required')
        text=text.replace(original,changed)
    return text
