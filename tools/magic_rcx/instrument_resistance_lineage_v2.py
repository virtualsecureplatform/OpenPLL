"""Extend lineage observation to native topological area transfers."""
import re
from instrument_resistance_lineage import instrument_sources as base_instrument


def instrument_sources(sources):
    changed = base_instrument(sources)
    macro = r'''
#define OPENPLL_RES_ADJUST(node, statement, addition, site) do { \
    float openpll_before = (node)->rn_float.rn_area; \
    float openpll_added = (addition); \
    statement; \
    openpllResLineage("res_area_adjust", node, NULL, (double)openpll_before, \
        (double)openpll_added, (double)(node)->rn_float.rn_area, 0.0, site); \
} while (0)
'''
    changed['resis.h'] += macro
    for name, expected in [('ResMerge.c', 9), ('ResSimple.c', 4)]:
        text = changed[name]
        pattern = r'\b(\w+)->rn_float\.rn_area\s*\+=\s*([^;]+);'
        matches = list(re.finditer(pattern, text))
        selected = []
        for m in matches:
            if name == 'ResMerge.c' and m.group(1) == 'node1' and m.group(2).strip() == 'node2->rn_float.rn_area':
                continue  # Already observed as an explicit node merge.
            selected.append(m)
        if len(selected) != expected:
            raise ValueError('pinned topological area update count differs: ' + name)
        for m in reversed(selected):
            node, expression = m.groups()
            site = name + ':' + str(text.count('\n', 0, m.start()) + 1)
            new = f'OPENPLL_RES_ADJUST({node}, {m.group(0)[:-1]}, ({expression}), "{site}");'
            text = text[:m.start()] + new + text[m.end():]
        changed[name] = text
    return changed
