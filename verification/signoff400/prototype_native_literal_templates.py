"""Share identical literal PDK calls without changing primitive equations.

The added subcircuits have no parameters or private nodes. Expanding each
generated call must reproduce its source terminals, model and literal
parameters exactly. Resistors and the outer interface remain unchanged.
"""
from decimal import Decimal, InvalidOperation

PREFIX = '__openpll_literal_leaf_'


def primitive(fields):
    positions = [i for i, f in enumerate(fields) if f.startswith('sky130_fd_pr__')]
    if len(positions) != 1 or positions[0] < 3:
        raise ValueError('one native PDK primitive model required')
    stop = positions[0]
    names = set()
    for item in fields[stop + 1:]:
        if item.count('=') != 1:
            raise ValueError('literal named primitive parameters required')
        name, value = item.split('=')
        try:
            finite = Decimal(value).is_finite()
        except InvalidOperation:
            finite = False
        if not name or name.lower() in names or not finite:
            raise ValueError('unique finite literal parameters required')
        names.add(name.lower())
    return fields[1:stop], fields[stop:]


def factor(text):
    lines = text.splitlines()
    if PREFIX in text.lower():
        raise ValueError('reserved template namespace collision')
    directives = [s.split() for s in lines if s.lstrip().startswith('.')]
    if len(directives) != 2 or directives[0][0].lower() != '.subckt' or directives[1][0].lower() != '.ends':
        raise ValueError('one flat outer subcircuit required')
    header, end = directives
    if end != ['.ends', header[1]] or any('=' in p or ':' in p for p in header[2:]):
        raise ValueError('parameterless outer scope with explicit matching end required')
    templates, rewritten, names, count = {}, [], set(), 0
    for line in lines:
        fields = line.split()
        if not fields or fields[0].startswith(('*', '.')):
            rewritten.append(line)
            continue
        name = fields[0]
        if name.lower() in names:
            raise ValueError('duplicate element name')
        names.add(name.lower())
        if name[0].lower() == 'r':
            rewritten.append(line)
            continue
        if not name.startswith('Xflat'):
            raise ValueError('only explicit native flat primitives and resistors supported')
        nodes, model = primitive(fields)
        key = (len(nodes), tuple(model))
        if key not in templates:
            templates[key] = PREFIX + str(len(templates))
        rewritten.append(' '.join([name, *nodes, templates[key]]))
        count += 1
    definitions = []
    for (arity, model), name in templates.items():
        ports = ['p' + str(i) for i in range(arity)]
        definitions.extend(['.subckt ' + ' '.join([name, *ports]),
                            ' '.join(['Xdevice', *ports, *model]), '.ends ' + name])
    result = '* Literal native primitive templates; no electrical reduction.\n' + '\n'.join(definitions + rewritten) + '\n'
    review(text, result)
    return result, dict(primitives=count, literal_templates=len(templates))


def review(original, generated):
    """Independently expand actual emitted definitions and compare all cards."""
    definitions, root, active = {}, [], None
    for line in generated.splitlines():
        f = line.split()
        if not f or f[0].startswith('*'):
            continue
        if f[0] == '.subckt' and f[1].startswith(PREFIX):
            if active is not None or f[1] in definitions:
                raise ValueError('invalid or duplicate literal template')
            active = (f[1], f[2:], [])
        elif active is not None:
            if f[0] == '.ends':
                name, ports, cards = active
                if f != ['.ends', name] or len(cards) != 1 or len(ports) != len(set(ports)):
                    raise ValueError('one primitive per parameterless literal template required')
                nodes, model = primitive(cards[0])
                if nodes != ports:
                    raise ValueError('template must expose every primitive terminal in order')
                definitions[name] = (ports, model)
                active = None
            else:
                active[2].append(f)
        else:
            root.append(f)
    if active is not None:
        raise ValueError('unterminated literal template')
    expected = [s.split() for s in original.splitlines() if s.strip() and not s.lstrip().startswith('*')]
    actual = []
    used = set()
    for f in root:
        if f[0].startswith('Xflat'):
            if f[-1] not in definitions:
                raise ValueError('undefined literal template')
            ports, model = definitions[f[-1]]
            if len(f[1:-1]) != len(ports):
                raise ValueError('literal template call arity differs')
            used.add(f[-1])
            f = [f[0], *f[1:-1], *model]
        actual.append(f)
    if used != set(definitions) or actual != expected:
        raise ValueError('expanded actual cards differ from original primitive/resistor/interface cards')
    return True
