"""Documented nominal sheets including explicitly declared diffusion/tap aliases.

Device regions are deliberately absent: assigning their voltage basis requires
device-interface evidence beyond a nominal resist selector.
"""
from fractions import Fraction
import re
from nominal_sheet_resistance import parse as parse_interconnect

ADDED = {
    '(pwell,isosub)/well': ('pwell',),
    '(nwell)/well': ('nwell',),
    '(*ndiff,nsd)/active': ('ndiff', 'nsubdiff'),
    '(*pdiff,*psd)/active': ('pdiff', 'psubdiff'),
}
DECLARATIONS = {
    'pwell': ('well', 'pwell'), 'nwell': ('well', 'nwell'),
    'ndiff': ('active', 'ndiff'), 'pdiff': ('active', 'pdiff'),
    'nsubdiff': ('active', 'nsd'), 'psubdiff': ('active', 'psd'),
}


def parse(text):
    result = parse_interconnect(text)
    section = None
    declarations = {}
    extraction = ngspice = False
    variants = set()
    found = {}
    for raw in text.splitlines():
        line = raw.split('#', 1)[0].strip()
        if line == 'types':
            section = 'types'
            continue
        if line == 'extract':
            extraction = True
            continue
        if line == 'end':
            section = None
            extraction = False
            continue
        words = line.split()
        if section == 'types' and len(words) == 2:
            plane, aliases = words[0], words[1].split(',')
            if aliases[0] in DECLARATIONS:
                if aliases[0] in declarations:
                    raise ValueError('ambiguous material declaration')
                declarations[aliases[0]] = (plane, aliases)
        if not extraction:
            continue
        if line.startswith('style '):
            ngspice = words[1] == 'ngspice'
        if line.startswith('variants '):
            variants = set(re.findall(r'\((.*?)\)', line))
        if not (ngspice and variants == {'', 'orig', 'si'} and words and
                words[0] == 'resist' and words[1] in ADDED):
            continue
        if len(words) != 3 or words[1] in found:
            raise ValueError('ambiguous or adjusted nominal diffusion/well sheet')
        value = Fraction(words[2])
        if value <= 0:
            raise ValueError('positive nominal sheet required')
        found[words[1]] = value
    if set(found) != set(ADDED):
        raise ValueError('complete nominal diffusion/well selectors required')
    for canonical, (plane, alias) in DECLARATIONS.items():
        actual = declarations.get(canonical)
        if actual is None or actual[0] != plane or alias not in actual[1]:
            raise ValueError('explicit canonical material/plane/alias required: ' + canonical)
    for selector, materials in ADDED.items():
        for material in materials:
            result[material] = found[selector]
    return result
