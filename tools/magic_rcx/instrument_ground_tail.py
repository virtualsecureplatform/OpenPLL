"""Observe the native halo-tail ground subtraction and its clipped geometry."""
from instrument_ground_halo import instrument_with_ground_halo
DECLARATION='static void openpllGroundTail(NodeRegion *, Boundary *, Rect *, int, int, double, double, double, double, int);\n'
IMPLEMENTATION=r'''
static void openpllGroundTail(NodeRegion *node, Boundary *bp, Rect *clip,
    int distance, int length, double multiplier, double fraction,
    double coefficient, double subcap, int split)
{
    FILE *f = openpllTraceFile;
    Rect *edge = &bp->b_segment;
    if (!f) return;
    fprintf(f, "{\"kind\":\"ground_halo_tail\",\"cell\":");
    openpllTraceString(f, openpllTraceCell);
    fprintf(f, ",\"epoch\":%lu,\"node_id\":\"%p\",\"boundary\":[%d,%d,%d,%d],\"clip\":[%d,%d,%d,%d],\"direction\":%d,\"distance\":%d,\"length\":%d,\"native_float_multiplier_hex\":\"%a\",\"fraction_hex\":\"%a\",\"coefficient_hex\":\"%a\",\"subcap_hex\":\"%a\",\"split\":%s,\"pointwise_placement_qualified\":false}\n",
        openpllTraceEpoch, (void *)node, edge->r_xbot, edge->r_ybot,
        edge->r_xtop, edge->r_ytop, clip->r_xbot, clip->r_ybot,
        clip->r_xtop, clip->r_ytop, bp->b_direction, distance, length,
        multiplier, fraction, coefficient, subcap, split ? "true" : "false");
}
'''

def instrument_with_ground_tail(sources):
    changed,inventory=instrument_with_ground_halo(sources)
    text=changed['ExtCouple.c'];marker='OPENPLL_GROUND_ADD(rbp, rbp->nreg_cap -= subcap, "ExtCouple.c:1254");'
    if text.count(marker)!=1:raise ValueError('one unchanged native halo-tail subtraction required')
    call='openpllGroundTail(rbp, bp, clip, dnear, length, (double)mult, snear, (double)ExtCurStyle->exts_perimCap[ta][tb], (double)subcap, IsSplit(bp->b_inside));'
    text=text.replace(marker,'do { '+call+' '+marker+' } while (0);')
    anchor='#include "fringe_support_trace.h"'
    if text.count(anchor)!=1:raise ValueError('one diagnostic declaration anchor required')
    changed['ExtCouple.c']=text.replace(anchor,anchor+'\n'+DECLARATION)+IMPLEMENTATION
    return changed,inventory
