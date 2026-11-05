"""Conservative material envelope from exposed OpenDB wire-decoder geometry.

Decoder semantics are checked against the native OpenROAD revision:
https://github.com/The-OpenROAD-Project/OpenROAD/blob/dcf36133a369abc8f3c5e5738cd4d82e4903c0e0/src/odb/include/odb/dbWireCodec.h
The envelope includes widths, endpoint extensions, via boxes and RECT patches.
It is used for fill selection, not a claim of exact routed polygon identity.
"""


def envelope(points, widths, extensions, via_boxes, patches):
    if not points or not widths or any(w <= 0 for w in widths):
        raise ValueError('nonempty route points and positive native widths required')
    if any(e < 0 for e in extensions):
        raise ValueError('nonnegative endpoint extensions required')
    radius = max([(w + 1) // 2 for w in widths] + list(extensions) + [0])
    for box in via_boxes:
        x1, y1, x2, y2 = box
        if x1 > x2 or y1 > y2:
            raise ValueError('ordered local via box required')
        # L1 bounds each corner's distance under any via rotation/reflection.
        radius = max(radius, *(abs(x) + abs(y) for x in (x1, x2) for y in (y1, y2)))
    boxes = [[x - radius, y - radius, x + radius, y + radius] for x, y in points]
    for box in patches:
        if box[0] > box[2] or box[1] > box[3]:
            raise ValueError('ordered absolute patch rectangle required')
        boxes.append(list(box))
    return [min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes)], radius


def decode(odb, wire):
    decoder = odb.dbWireDecoder(); decoder.begin(wire)
    points, widths, extensions, vias, patches, links = [], [], [], [], [], []
    point = None; junctions = {}; segments = []
    def width():
        layer = decoder.getLayer()
        widths.extend(w for w in (layer.getWidth(), layer.getWrongWayWidth()) if w > 0)
    while True:
        op = decoder.next()
        if op == decoder.END_DECODE:
            break
        if op in (decoder.PATH, decoder.SHORT, decoder.VWIRE):
            point = None; width()
            if op == decoder.SHORT:
                links.append(dict(opcode=str(op), junction=decoder.getJunctionValue()))
            elif op == decoder.VWIRE:
                links.append(dict(opcode=str(op)))
        elif op == decoder.JUNCTION:
            point = junctions[decoder.getJunctionValue()]; width()
        elif op in (decoder.POINT, decoder.POINT_EXT):
            values = decoder.getPoint() if op == decoder.POINT else decoder.getPoint_ext()
            previous = point; point = tuple(values[:2]); points.append(point)
            if previous is not None and previous != point:
                if previous[0] != point[0] and previous[1] != point[1]:
                    raise ValueError('non-Manhattan route needs a separate material bound')
                segments.append([*previous, *point])
            junctions[decoder.getJunctionId()] = point
            if op == decoder.POINT_EXT:
                extensions.append(values[2])
        elif op == decoder.RULE:
            widths.append(decoder.getRule().getWidth())
        elif op in (decoder.VIA, decoder.TECH_VIA):
            if point is None:
                raise ValueError('via without a preceding physical point')
            via = decoder.getVia() if op == decoder.VIA else decoder.getTechVia()
            boxes = list(via.getBoxes())
            if not boxes:
                raise ValueError('via without native material rectangles')
            vias.extend([b.xMin(), b.yMin(), b.xMax(), b.yMax()] for b in boxes)
            points.append(point); junctions[decoder.getJunctionId()] = point; width()
        elif op == decoder.RECT:
            if point is None:
                raise ValueError('patch without a preceding physical point')
            x1, y1, x2, y2 = decoder.getRect()
            patches.append([point[0] + x1, point[1] + y1, point[0] + x2, point[1] + y2])
        elif op in (decoder.ITERM, decoder.BTERM):
            pass
        else:
            raise ValueError('unreviewed native wire opcode: ' + str(op))
    box, radius = envelope(points, widths, extensions, vias, patches)
    return dict(bbox_nm=box, conservative_radius_nm=radius, points_nm=points, segments_nm=segments,
                widths_nm=widths, extensions_nm=extensions, local_via_boxes_nm=vias,
                absolute_patch_boxes_nm=patches, nonphysical_path_links=links,
                exact_wire_polygon_identity_claimed=False)


def region_boxes(trace, offset, margin_nm):
    if margin_nm < 0:
        raise ValueError('nonnegative neighborhood margin required')
    radius = trace['conservative_radius_nm'] + margin_nm
    dx, dy = offset
    boxes = [[x+dx-radius,y+dy-radius,x+dx+radius,y+dy+radius] for x,y in trace['points_nm']]
    for x1,y1,x2,y2 in trace['segments_nm']:
        boxes.append([min(x1,x2)+dx-radius,min(y1,y2)+dy-radius,
                      max(x1,x2)+dx+radius,max(y1,y2)+dy+radius])
    boxes.extend([x1+dx-margin_nm,y1+dy-margin_nm,x2+dx+margin_nm,y2+dy+margin_nm]
                 for x1,y1,x2,y2 in trace['absolute_patch_boxes_nm'])
    return boxes
