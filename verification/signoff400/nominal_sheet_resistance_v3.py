"""Resolve nominal gate-region sheet selectors through explicit alias paths.

An extraction rule value does not establish a valid transistor interface or a
physical gate resistance model. Those qualifications remain separate.
"""
from nominal_sheet_resistance_v2 import parse as parse_nondevice

GATE_TYPES = ('scnmos', 'scpmos', 'scnmoslvt', 'scpmoshvt')


def gate_selector_paths(text):
    section = None
    names, aliases, planes = {}, {}, {}
    for raw in text.splitlines():
        line = raw.split('#', 1)[0].strip()
        if line in ('types', 'aliases'):
            section = line
            continue
        if line == 'end':
            section = None
        words = line.split()
        if len(words) != 2:
            continue
        if section == 'types':
            canonical = words[1].split(',')[0]
            for token in words[1].split(','):
                if token in names:
                    raise ValueError('ambiguous native type alias')
                names[token] = canonical
            planes[canonical] = words[0].lstrip('-')
        elif section == 'aliases':
            if words[0] in aliases:
                raise ValueError('ambiguous layer alias')
            aliases[words[0]] = words[1].split(',')

    def path(token, target, visiting):
        if token.startswith('*'):
            return None  # No inference about contact/wildcard expansion.
        if token in visiting:
            raise ValueError('cyclic selector alias')
        if token in names:
            return [token, target] if names[token] == target else None
        if token not in aliases:
            raise ValueError('unknown selector alias: '+token)
        for child in aliases[token]:
            found = path(child, target, visiting | {token})
            if found:
                return [token, *found]
        return None

    result = {}
    for target in GATE_TYPES:
        if planes.get(target) != 'active':
            raise ValueError('native gate material must be on active plane')
        found = path('allpolynonres', target, set())
        if not found:
            raise ValueError('gate material absent from explicit poly sheet selector: '+target)
        result[target] = found
    return result


def parse(text):
    result = parse_nondevice(text)
    for target in gate_selector_paths(text):
        result[target] = result['poly']
    return result
