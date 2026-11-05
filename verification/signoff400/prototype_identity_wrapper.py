"""Remove a parameterless outer SPICE namespace with identity-connected ports.

This applies only to the explicit primitive/resistor DC control. It does not
flatten PDK device subcircuits or evaluate/change their parameters.
"""


def lift(text, instance, outside_names=()):
    lines = text.splitlines()
    substantive = [(i, s.split()) for i, s in enumerate(lines)
                   if s.strip() and not s.lstrip().startswith('*')]
    if len(substantive) < 3:
        raise ValueError('nonempty outer subcircuit required')
    first, header = substantive[0]
    last, end = substantive[-1]
    if header[0].lower() != '.subckt' or len(header) < 3:
        raise ValueError('one outer subcircuit required')
    master, ports = header[1], header[2:]
    if any('=' in p or ':' in p for p in ports) or len({p.lower() for p in ports}) != len(ports):
        raise ValueError('unique ports and no wrapper parameters required')
    if [x.lower() for x in end] != ['.ends', master.lower()]:
        raise ValueError('matching explicit outer end required')
    call = instance.split()
    if not call or call[0][0].lower() != 'x' or call[1:] != [*ports, master]:
        raise ValueError('exact identity port connection without instance parameters required')
    names = {s.lower() for s in outside_names}
    count = 0
    for _, fields in substantive[1:-1]:
        name = fields[0]
        if name[0].lower() not in ('x', 'r') or name.lower() in names:
            raise ValueError('unique primitive/resistor cards without scoped directives required')
        if name[0].lower() == 'x' and not any(f.startswith('sky130_fd_pr__') for f in fields[1:]):
            raise ValueError('only native PDK primitive calls may remain')
        names.add(name.lower())
        count += 1
    body = '\n'.join(s for i, s in enumerate(lines) if i not in (first, last)) + '\n'
    return body, count
