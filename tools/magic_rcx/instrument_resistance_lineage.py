"""Trace unsimplified node-area lineage, scaling and existing output names."""
from instrument_resistance_area import instrument


def instrument_sources(sources):
    changed = dict(sources)
    changed['ResMakeRes.c'] = instrument(sources['ResMakeRes.c']).replace(
        '#include "resistance_area_trace.h"', '#include "resistance_lineage_trace.h"')
    def replace(file, old, new):
        if changed[file].count(old) != 1:
            raise ValueError('pinned resistance lineage layout differs: ' + file + ': ' + old[:60])
        changed[file] = changed[file].replace(old, new)
    declarations = '''
extern void openpllResLineage(const char *, resNode *, resNode *,
    double, double, double, double, const char *);
extern void openpllResScaleNode(resNode *, double);
'''
    # Prototype precedes InitializeResNode, after the resNode typedef.
    replace('resis.h', '/* Macros */', declarations + '\n/* Macros */')
    replace('resis.h', '\t  (node)->rn_re = (resElement *) NULL;\\\n}',
            '\t  (node)->rn_re = (resElement *) NULL;\\\n'
            '\t  openpllResLineage("res_node_init", node, NULL, 0.0, 0.0, 0.0, 0.0, NULL);\\\n}')
    old = '    node1->rn_float.rn_area += node2->rn_float.rn_area;'
    replace('ResMerge.c', old, '''    {
        double trace_before = (double)node1->rn_float.rn_area;
        double trace_source = (double)node2->rn_float.rn_area;
''' + old + '''
        openpllResLineage("res_node_merge", node1, node2, trace_before,
            trace_source, (double)node1->rn_float.rn_area, 0.0, NULL);
    }''')
    replace('ResSimple.c', '    capperarea = totalcap / totalarea;',
            '    capperarea = totalcap / totalarea;\n'
            '    openpllResLineage("res_distribution_scale", NULL, NULL, (double)totalarea,\n'
            '        (double)totalcap, (double)capperarea, 0.0, NULL);')
    replace('ResSimple.c', '\ttotalarea += workingNode->rn_float.rn_area;',
            '\ttotalarea += workingNode->rn_float.rn_area;\n'
            '        openpllResLineage("res_distribution_input", workingNode, NULL, 0.0,\n'
            '            0.0, (double)workingNode->rn_float.rn_area, 0.0, NULL);')
    replace('ResSimple.c', 'workingNode->rn_float.rn_area *= capperarea;',
            'openpllResScaleNode(workingNode, (double)capperarea);')
    # Preserve the original native float multiplication, with factor cast back
    # to the float type of capperarea before applying it.
    changed['ResMakeRes.c'] += '''
void openpllResScaleNode(resNode *node, double factor)
{
    float native_factor = (float)factor;
    OPENPLL_RES_SCALE(node, native_factor);
}
'''
    old = '    /* Create "rnode" entries for each subnode */'
    if changed['ResPrint.c'].count(old) != 1:
        raise ValueError('pinned resistance writer differs')
    # Emit after existing naming and immediately before the native writer.
    marker = '\t    /* rnode name R C x y  type (R is always 0) */'
    replace('ResPrint.c', marker, '''        openpllResLineage("res_node_output", snode, NULL, 0.0,
            (double)(snode->rn_float.rn_area / ExtCurStyle->exts_capScale),
            (double)snode->rn_float.rn_area, (double)ExtCurStyle->exts_capScale,
            snode->rn_name);
''' + marker)
    return changed
