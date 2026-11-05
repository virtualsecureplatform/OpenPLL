"""Resolve retained native placement paths against the manufacturing GDS."""
import json


def transform_key(trans, pya):
    origin = trans * pya.Point(0, 0)
    x = trans * pya.Point(1, 0)
    y = trans * pya.Point(0, 1)
    return (x.x - origin.x, y.x - origin.x, origin.x,
            x.y - origin.y, y.y - origin.y, origin.y)


def native_key(placement, grid_nm):
    master, a, b, x, c, d, y = placement
    if (a * a + c * c, b * b + d * d, a * b + c * d) != (1, 1, 0):
        raise ValueError('non-orthogonal native placement')
    return master, (a, b, x * grid_nm, c, d, y * grid_nm)


def resolve_windows(layout, top, metadata, selected, grid_nm, margin_nm, pya):
    if grid_nm != int(grid_nm) or grid_nm <= 0:
        raise ValueError('exact integral native-to-GDS grid required')
    chosen = [r for r in metadata['physical_instances'] if r['instance'] in set(selected)]
    if {r['instance'] for r in chosen} != set(selected):
        raise ValueError('selected primitives absent from physical reference')
    paths = {json.dumps(r['physical_hierarchy_identity']): r['physical_hierarchy_identity'] for r in chosen}
    indexes = {}
    window = pya.Region()
    bounds = []
    for identity in paths.values():
        cell = top
        global_transform = pya.Trans()
        for master, scale, placement in identity:
            if cell.name != master:
                raise ValueError('native and GDS hierarchy masters differ')
            index = cell.cell_index()
            if index not in indexes:
                items = {}
                for instance in cell.each_inst():
                    for trans in instance.cell_inst.each_trans():
                        key = (instance.cell.name, transform_key(trans, pya))
                        items.setdefault(key, []).append((instance.cell, trans))
                indexes[index] = items
            key = native_key(placement, int(grid_nm))
            found = indexes[index].get(key, [])
            if len(found) != 1:
                raise ValueError('native physical cell has no unique GDS placement: ' + repr(key))
            cell, trans = found[0]
            global_transform = global_transform * trans
        box = cell.bbox().transformed(global_transform)
        if box.empty():
            raise ValueError('selected physical cell has empty GDS geometry')
        window.insert(box.enlarged(margin_nm))
        bounds.append(dict(master=cell.name, bbox_nm=[box.left, box.bottom, box.right, box.top],
                           physical_hierarchy_identity=identity))
    return window.merged(), bounds
