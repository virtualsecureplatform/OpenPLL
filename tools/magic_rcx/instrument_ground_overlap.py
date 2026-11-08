"""Link native ground-area shielding subtraction to resolved overlap support."""
from instrument_ground_support import instrument_with_ground_support

IMPLEMENTATION = r'''
static void openpllGroundOverlap(NodeRegion *node, unsigned long overlap_id,
    int area, double coefficient)
{
    FILE *f = openpllTraceFile;
    if (!f) return;
    fprintf(f, "{\"kind\":\"ground_overlap_subtraction\",\"cell\":");
    openpllTraceString(f, openpllTraceCell);
    fprintf(f, ",\"epoch\":%lu,\"overlap_id\":%lu,\"node_id\":\"%p\",\"native_area\":%d,\"coefficient_hex\":\"%a\",\"pointwise_placement_qualified\":false}\n",
        openpllTraceEpoch, overlap_id, (void *)node, area, coefficient);
}
'''


def instrument_with_ground_overlap(sources):
    changed,inventory=instrument_with_ground_support(sources)
    rows=[r for r in inventory if r['file']=='ExtCouple.c' and r['statement']=='rabove->nreg_cap -= ExtCurStyle->exts_areaCap[ta] * ov.o_area;']
    if len(rows)!=1:raise ValueError('one native area shielding subtraction required')
    row=rows[0];site='ExtCouple.c:'+str(row['line']);old=f'OPENPLL_GROUND_ADD(rabove, {row["statement"][:-1]}, "{site}");'
    text=changed['ExtCouple.c']
    if text.count(old)!=1:raise ValueError('unchanged native shielding subtraction required')
    text=text.replace(old,'do { openpllGroundOverlap(rabove, openpllOverlapId, ov.o_area, (double)ExtCurStyle->exts_areaCap[ta]); '+old+' } while (0);')
    anchor='#include "fringe_support_trace.h"'
    if text.count(anchor)!=1:raise ValueError('one resolved support header required')
    text=text.replace(anchor,anchor+'\nstatic void openpllGroundOverlap(NodeRegion *, unsigned long, int, double);')
    changed['ExtCouple.c']=text+IMPLEMENTATION
    return changed,inventory
