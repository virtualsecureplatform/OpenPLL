"""Extend coupling diagnostics with an ordered numerical ground-capacitance ledger.

This records native mutations, not a spatial redistribution model. Apply only to
an isolated copy of the verified source, never a live or release installation.
"""
import re
from instrument_coupling_geometry import instrument

DECLARATIONS = '''
extern void openpllGroundBegin(const char *);
extern void openpllGroundUpdate(NodeRegion *, const char *, int, double, double);
extern void openpllGroundOutput(NodeRegion *, const char *, int, double);
#define OPENPLL_GROUND_ADD(node, statement, site) do { \\
    double openpll_before = (double)(node)->nreg_cap; \\
    statement; \\
    openpllGroundUpdate(node, site, 1, openpll_before, (double)(node)->nreg_cap); \\
} while (0)
#define OPENPLL_GROUND_RESET(node, statement, site) do { \\
    statement; \\
    openpllGroundUpdate(node, site, 0, 0.0, (double)(node)->nreg_cap); \\
} while (0)
'''

IMPLEMENTATION = r'''
/* Shared writer keeps events in native execution order across source files. */
void openpllGroundBegin(const char *cell)
{
    const char *path;
    openpllTraceCell = cell;
    openpllTraceEpoch++;
    if (!openpllTraceInitialized) {
        openpllTraceInitialized = 1;
        path = getenv("OPENPLL_COUPLING_TRACE");
        if (path && *path) {
            openpllTraceFile = fopen(path, "w");
            if (!openpllTraceFile) perror("OPENPLL_COUPLING_TRACE");
            else setvbuf(openpllTraceFile, openpllTraceBuffer, _IOFBF,
                         sizeof(openpllTraceBuffer));
        }
    }
}
void openpllGroundUpdate(NodeRegion *node, const char *site,
    int has_before, double before, double after)
{
    FILE *f = openpllTraceFile;
    if (!f) return;
    fprintf(f, "{\"kind\":\"ground_update\",\"cell\":");
    openpllTraceString(f, openpllTraceCell);
    fprintf(f, ",\"epoch\":%lu,\"node_id\":\"%p\",\"site\":",
            openpllTraceEpoch, (void *)node);
    openpllTraceString(f, site);
    fprintf(f, ",\"has_before\":%s,\"before_hex\":\"%a\",\"after_hex\":\"%a\"}\n",
            has_before ? "true" : "false", before, after);
}
void openpllGroundOutput(NodeRegion *node, const char *name,
    int substrate, double emitted)
{
    FILE *f = openpllTraceFile;
    if (!f) return;
    fprintf(f, "{\"kind\":\"ground_output\",\"cell\":");
    openpllTraceString(f, openpllTraceCell);
    fprintf(f, ",\"epoch\":%lu,\"node_id\":\"%p\",\"name\":",
            openpllTraceEpoch, (void *)node);
    openpllTraceString(f, name);
    fprintf(f, ",\"substrate\":%s,\"native_hex\":\"%a\",\"scale_hex\":\"%a\",\"emitted_hex\":\"%a\"}\n",
            substrate ? "true" : "false", (double)node->nreg_cap,
            (double)ExtCurStyle->exts_capScale, emitted);
}
'''


def instrument_sources(sources):
    """Return three transformed sources and a complete direct-write inventory."""
    result = dict(sources)
    inventory = []
    expected = {'ExtBasic.c': 9, 'ExtCouple.c': 8, 'ExtRegion.c': 1}
    for name, count in expected.items():
        text = sources[name]
        matches = list(re.finditer(r'\b(\w+)->nreg_cap\s*(\+=|-=|=)\s*([^;]+);', text))
        if len(matches) != count:
            raise ValueError('pinned ground mutation layout differs: ' + name)
        for m in reversed(matches):
            node, op, _ = m.groups()
            line = text.count('\n', 0, m.start()) + 1
            site = name + ':' + str(line)
            macro = 'OPENPLL_GROUND_RESET' if op == '=' else 'OPENPLL_GROUND_ADD'
            replacement = f'{macro}({node}, {m.group(0)[:-1]}, "{site}");'
            text = text[:m.start()] + replacement + text[m.end():]
            inventory.append(dict(file=name, line=line, statement=m.group(0), reset=op == '='))
        result[name] = text
    # Keep one extraction epoch for both node construction and coupling phases.
    result['ExtCouple.c'] = instrument(result['ExtCouple.c']).replace(
        '    openpllTraceCell = def->cd_name;\n    openpllTraceEpoch++;', '')
    result['ExtCouple.c'] += IMPLEMENTATION
    marker = '    glob_subsnode = (NodeRegion *)NULL;'
    if result['ExtBasic.c'].count(marker) != 1:
        raise ValueError('pinned extraction entry differs')
    result['ExtBasic.c'] = result['ExtBasic.c'].replace(marker, '    openpllGroundBegin(def->cd_name);\n' + marker)
    # Observe names and emitted values only at existing native output sites.
    pairs = [
        ('fprintf(outFile, "substrate \\"%s\\" 0 0", text);', 'openpllGroundOutput(reg, text, 1, 0.0);'),
        ('fprintf(outFile, "node \\"%s\\" %d %lg", text, intR, finC);', 'openpllGroundOutput(reg, text, 0, finC);'),
    ]
    for old, addition in pairs:
        if result['ExtBasic.c'].count(old) != 1:
            raise ValueError('pinned ground output differs: ' + old)
        result['ExtBasic.c'] = result['ExtBasic.c'].replace(old, old + '\n        ' + addition)
    for name in result:
        marker = '#include "extract/extractInt.h"'
        if result[name].count(marker) != 1:
            raise ValueError('header insertion anchor missing: ' + name)
        result[name] = result[name].replace(marker, marker + '\n' + DECLARATIONS)
    return result, sorted(inventory, key=lambda r: (r['file'], r['line']))
