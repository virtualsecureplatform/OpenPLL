"""Finite unit-sheet basis for tiles with one native voltage and no R chain.

Actual anchor coordinates remain fixed. All other mesh points receive latent
voltages, rather than extending the native constant voltage over the tile.
Native DC preservation does not qualify contact or material/PVT physics.
"""
from collections import defaultdict
from fractions import Fraction as F
from floating_sheet_basis import mesh, certify


def prepare(box, anchors, namespace, refinement=1, split=0):
    box = list(map(F, box))
    if len(box) != 4 or box[0] >= box[2] or box[1] >= box[3] or split != 0:
        raise ValueError('positive unsplit rectangular tile required')
    if not namespace or not anchors:
        raise ValueError('native anchor and fresh namespace required')
    locations = {}
    for point, name in anchors:
        point = tuple(map(F, point))
        if len(point) != 2 or not name or not (box[0] <= point[0] <= box[2] and box[1] <= point[1] <= box[3]):
            raise ValueError('actual native anchor must be inside closed tile')
        if point in locations and locations[point] != name:
            raise ValueError('coincident anchors have distinct native identities')
        locations[point] = name
    native = set(locations.values())
    if len(native) != 1:
        raise ValueError('single native voltage required; multiple ports need native R matching')
    xs = sorted({box[0], box[2], *(p[0] for p in locations)})
    ys = sorted({box[1], box[3], *(p[1] for p in locations)})
    if refinement not in (1, 2, 4, 8, 16) or ((len(xs)-1)*refinement+1)*((len(ys)-1)*refinement+1) > 4096:
        raise ValueError('supported bounded mesh refinement required')
    # Collinear boundary vertices introduce every actual anchor cut without
    # modifying the frozen exact P1 mesher or its geometry certificates.
    hull = ([(x, box[1]) for x in xs] + [(box[2], y) for y in ys[1:]] +
            [(x, box[3]) for x in reversed(xs[:-1])] +
            [(box[0], y) for y in reversed(ys[1:-1])])
    template = mesh(hull, refinement=refinement)
    certificate = certify(template)
    point_nodes = [locations.get(tuple(point), namespace+':'+str(i))
                   for i, point in enumerate(template['points'])]
    latent = [name for point, name in zip(template['points'], point_nodes) if tuple(point) not in locations]
    if len(set(latent)) != len(latent) or native & set(latent):
        raise ValueError('generated/native voltage identity collision')
    template['point_nodes'] = point_nodes
    def named(matrix):
        result = defaultdict(F)
        for (a, b), value in matrix.items():
            result[point_nodes[a], point_nodes[b]] += value
        return {key: value for key, value in result.items() if value}
    conductance, mass = named(template['stiffness']), named(template['mass'])
    return dict(template=template, native_nodes=sorted(native), latent_nodes=latent,
                conductance=conductance, unit_area_mass=mass, geometric_certificate=certificate,
                actual_anchor_coordinates_preserved=True, native_resistors_added_or_rewritten=False,
                resistance_PVT_qualified=False, physical_RC_qualified=False, release_qualified=False)


def reference_mass(model, reference='REF'):
    if reference in set(model['native_nodes']) | set(model['latent_nodes']):
        raise ValueError('reference identity collides with sheet')
    result = defaultdict(F, model['unit_area_mass'])
    for (a, b), value in model['unit_area_mass'].items():
        result[a, reference] -= value
        result[reference, b] -= value
        result[reference, reference] += value
    return {key: value for key, value in result.items() if value}
