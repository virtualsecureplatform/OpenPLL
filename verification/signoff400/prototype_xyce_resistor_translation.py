"""Translate the pinned SKY130 poly resistor wrapper, without editing the PDK.

Diagnostic backend adapter. Native comparisons are required before adoption.
ngspice RESupdate_conduct uses RSH*(L-2*SHORT)/(W-2*DW); the pinned
poly model has SHORT=0 and DW=-TOL_POLY/2-POLY_DW/2. Its wrapper's drawn
L/W values are micrometres because the pinned all.spice selects SCALE=1u.
Xyce NARROW affects both dimensions, so it cannot express this by renaming DW.
"""
from decimal import Decimal, InvalidOperation


MODEL = 'sky130_fd_pr__res_generic_po'
WRAPPER = '__openpll_xyce_poly_resistor'
DEFINITION = '''
* Pinned ngspice poly-resistor equation; drawn L/W are in micrometres.
.model __openpll_xyce_poly_temperature R TC1={tc1rsgpu} TC2={tc2rsgpu} TNOM=30
.subckt __openpll_xyce_poly_resistor p n w=1 l=1
Rnative p n __openpll_xyce_poly_temperature R={rp1*(l*1e-6)/(w*1e-6+tol_poly+poly_dw)}
.ends __openpll_xyce_poly_resistor
'''


def translate(text):
    """Replace only literal, positive L/W calls to the exact two-port wrapper."""
    if '__openpll_xyce_poly_' in text.lower():
        raise ValueError('adapter namespace already present')
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
            raise ValueError('expected a literal two-port poly resistor call')
        values = {}
        for token in f[4:]:
            if token.count('=') != 1:
                raise ValueError('literal named geometry required')
            name, value = token.lower().split('=')
            if name not in ('l', 'w') or name in values:
                raise ValueError('unsupported or duplicate resistor parameter')
            try:
                number = Decimal(value)
            except InvalidOperation as error:
                raise ValueError('finite literal resistor geometry required') from error
            if not number.is_finite() or number <= 0:
                raise ValueError('positive finite resistor geometry required')
            values[name] = number
        if set(values) != {'l', 'w'}:
            raise ValueError('explicit L and W required')
        f[3] = WRAPPER
        lines.append(' '.join(f))
        count += 1
    if not count:
        raise ValueError('no supported poly resistor instances')
    return DEFINITION + '\n'.join(lines) + '\n', count
