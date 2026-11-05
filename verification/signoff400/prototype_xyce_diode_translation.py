"""Geometry-limited calls to a separately supplied fixed-temperature diode model.

The model equations are supplied by the existing SKY130 diode comparison
implementation. This module authorizes neither a model nor release adoption.
"""
from decimal import Decimal, InvalidOperation

MODEL = 'sky130_fd_pr__diode_pw2nd_05v5'
WRAPPER = '__openpll_xyce_pw2nd'
GEOMETRIES = {(Decimal('0.4347'), Decimal('2.64')),
              (Decimal('0.6417'), Decimal('3.24'))}
DEFINITION = '''
* Explicit ngspice-47 diode geometry; fixed-temperature model required.
.subckt __openpll_xyce_pw2nd p n area=0 perim=0
Dnative p n openpll_pw2nd_candidate AREA={area} PJ={perim}
.ends __openpll_xyce_pw2nd
'''


def translate(text):
    if WRAPPER in text.lower():
        raise ValueError('diode adapter namespace already present')
    lines, count = [], 0
    for line in text.splitlines():
        f = line.split()
        if not f or f[0].startswith(('*', '.')):
            lines.append(line)
            continue
        positions = [i for i, word in enumerate(f) if word.lower() == MODEL]
        if not positions:
            lines.append(line)
            continue
        if positions != [3] or not f[0].lower().startswith('x'):
            raise ValueError('expected a two-port diode wrapper call')
        values = {}
        for token in f[4:]:
            if token.count('=') != 1:
                raise ValueError('literal named diode geometry required')
            name, value = token.lower().split('=')
            if name not in ('area', 'perim') or name in values:
                raise ValueError('unsupported or duplicate diode parameter')
            try:
                number = Decimal(value)
            except InvalidOperation as error:
                raise ValueError('finite literal diode geometry required') from error
            if not number.is_finite():
                raise ValueError('finite literal diode geometry required')
            values[name] = number
        if set(values) != {'area', 'perim'} or (values['area'], values['perim']) not in GEOMETRIES:
            raise ValueError('diode geometry outside comparison scope')
        f[3] = WRAPPER
        lines.append(' '.join(f))
        count += 1
    if not count:
        raise ValueError('no supported diode instances')
    return DEFINITION + '\n'.join(lines) + '\n', count
