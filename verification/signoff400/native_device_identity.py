"""Bind every native primitive to a unique model and physical origin.

Unlike a primitive multiset comparison this rejects swapped device parameters
between physically distinct but otherwise identical instances.
"""
from audit_keeper_native_R_contraction import parse


def inventory(text):
    origins = {}
    seen = set()
    for line in text.splitlines():
        if not line.startswith('* OPENPLL_ORIGIN '):
            continue
        fields = line.split()
        if len(fields) != 8:
            raise ValueError('malformed native physical origin')
        name = fields[2].lower()
        origin = (fields[3].lower(), *(int(v) for v in fields[4:]))
        if name in origins or origin in seen:
            raise ValueError('duplicate native physical origin or instance')
        origins[name] = origin
        seen.add(origin)
    data = parse(text)
    names = [line.split()[0].lower() for line in text.splitlines()
             if line and line[0].lower() == 'x']
    if len(names) != len(data['devices']) or set(names) != set(origins):
        raise ValueError('every primitive requires exactly one physical origin')
    result = {}
    for name, device in zip(names, data['devices']):
        model, nodes, params = device
        origin = origins[name]
        if origin[0] != model:
            raise ValueError('origin model disagrees with native primitive')
        result[origin] = dict(instance=name, nodes=nodes, parameters=params)
    return result


def compare_parameters(reference, candidate):
    before, after = inventory(reference), inventory(candidate)
    if before.keys() != after.keys():
        raise ValueError('physical primitive population changed')
    changed = [origin for origin in before
               if before[origin]['parameters'] != after[origin]['parameters']]
    return dict(physical_device_count=len(before),
                physical_origins_unique=True,
                per_physical_device_parameters_match=not changed,
                changed_parameter_origins=changed)
