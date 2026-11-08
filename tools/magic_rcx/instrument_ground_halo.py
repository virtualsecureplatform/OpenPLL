"""Observe per-callback halo ground shielding and its exact native subtraction."""
from instrument_ground_overlap import instrument_with_ground_overlap

DECLARATION = '''
static void openpllGroundHalo(const char *, NodeRegion *, NodeRegion *, Boundary *, Rect *,
    int, double, double, double, double, double, int);
'''
IMPLEMENTATION = r'''
static void openpllGroundHalo(const char *kind, NodeRegion *node, NodeRegion *other,
    Boundary *bp, Rect *box, int length, double multiplier, double fraction,
    double shield, double coefficient, double subcap, int split)
{
    FILE *f = openpllTraceFile;
    Rect *edge = &bp->b_segment;
    if (!f) return;
    fprintf(f, "{\"kind\":\"%s\",\"cell\":", kind);
    openpllTraceString(f, openpllTraceCell);
    fprintf(f, ",\"epoch\":%lu,\"node_id\":\"%p\",\"other_node_id\":\"%p\",\"boundary\":[%d,%d,%d,%d],\"box\":[%d,%d,%d,%d],\"direction\":%d,\"length\":%d,\"multiplier_hex\":\"%a\",\"fraction_hex\":\"%a\",\"shield_hex\":\"%a\",\"coefficient_hex\":\"%a\",\"subcap_hex\":\"%a\",\"split\":%s,\"pointwise_placement_qualified\":false}\n",
        openpllTraceEpoch, (void *)node, (void *)other,
        edge->r_xbot, edge->r_ybot, edge->r_xtop, edge->r_ytop,
        box->r_xbot, box->r_ybot, box->r_xtop, box->r_ytop, bp->b_direction,
        length, multiplier, fraction, shield, coefficient, subcap, split ? "true" : "false");
}
'''


def instrument_with_ground_halo(sources):
    changed,inventory=instrument_with_ground_overlap(sources)
    text=changed['ExtCouple.c']
    start=text.index('\nextSideOverlapHalo(tp, dinfo, esws)')
    end=text.index('\nint\nextSideOverlap(',start)
    part=text[start:end]
    def emit(kind,subcap):
        return f'openpllGroundHalo("{kind}", rbp, rtp, bp, &sov.so_clip, length, mult, sfrac, subfrac, (double)ExtCurStyle->exts_perimCap[ta][0], {subcap}, IsSplit(tp) || IsSplit(bp->b_inside));'
    marker='    subfrac = 0.0;'
    if part.count(marker)!=1:raise ValueError('one native halo accumulator reset required')
    part=part.replace(marker,marker+'\n    '+emit('ground_halo_begin','0.0'))
    marker='    /* Add in the new capacitance. */'
    if part.count(marker)!=1:raise ValueError('one native halo rule-list completion required')
    part=part.replace(marker,'    '+emit('ground_halo_end','0.0')+'\n'+marker)
    row=[r for r in inventory if r['file']=='ExtCouple.c' and r['line']==1521]
    if len(row)!=1 or row[0]['statement']!='rbp->nreg_cap -= subcap;':raise ValueError('pinned halo subtraction differs')
    marker='OPENPLL_GROUND_ADD(rbp, rbp->nreg_cap -= subcap, "ExtCouple.c:1521");'
    if part.count(marker)!=1:raise ValueError('one unchanged native halo subtraction required')
    part=part.replace(marker,'do { '+emit('ground_halo_subtract','(double)subcap')+' '+marker+' } while (0);')
    text=text[:start]+part+text[end:]
    anchor='#include "fringe_support_trace.h"'
    changed['ExtCouple.c']=text.replace(anchor,anchor+'\n'+DECLARATION)+IMPLEMENTATION
    return changed,inventory
