"""Observe native area/perimeter support without changing ground arithmetic."""
from instrument_fringe_support import instrument_with_fringe

DECLARATION = '''
extern void openpllGroundSupport(NodeRegion *, Tile *, Tile *, Rect *,
    int, int, int, int, const char *, const char *, double, double);
'''
IMPLEMENTATION = r'''
void openpllGroundSupport(NodeRegion *node, Tile *tile, Tile *neighbor,
    Rect *clip, int plane, int residue, int other, int direction,
    const char *site, const char *measure_kind, double measure, double coefficient)
{
    FILE *f = openpllTraceFile;
    if (!f) return;
    fprintf(f, "{\"kind\":\"ground_support\",\"cell\":");
    openpllTraceString(f, openpllTraceCell);
    fprintf(f, ",\"epoch\":%lu,\"node_id\":\"%p\",\"site\":",
        openpllTraceEpoch, (void *)node);
    openpllTraceString(f, site);
    fprintf(f, ",\"measure_kind\":");
    openpllTraceString(f, measure_kind);
    fprintf(f, ",\"plane\":%d,\"residue\":%d,\"other_residue\":%d,\"direction\":%d,\"tile\":[%d,%d,%d,%d],\"split\":%s,\"neighbor_split\":%s,\"neighbor\":",
        plane, residue, other, direction, LEFT(tile), BOTTOM(tile), RIGHT(tile), TOP(tile),
        IsSplit(tile) ? "true" : "false", neighbor && IsSplit(neighbor) ? "true" : "false");
    if (neighbor) fprintf(f, "[%d,%d,%d,%d]", LEFT(neighbor), BOTTOM(neighbor), RIGHT(neighbor), TOP(neighbor));
    else fprintf(f, "null");
    fprintf(f, ",\"clip\":");
    if (clip) fprintf(f, "[%d,%d,%d,%d]", clip->r_xbot, clip->r_ybot, clip->r_xtop, clip->r_ytop);
    else fprintf(f, "null");
    fprintf(f, ",\"native_measure_hex\":\"%a\",\"coefficient_hex\":\"%a\",\"pointwise_placement_qualified\":false}\n", measure, coefficient);
}
'''


def instrument_with_ground_support(sources):
    changed, inventory = instrument_with_fringe(sources)
    text = changed['ExtBasic.c']
    selected = [r for r in inventory if r['file']=='ExtBasic.c' and not r['reset']]
    if len(selected)!=6 or selected[0]['statement']!='reg->nreg_cap += area * ExtCurStyle->exts_areaCap[residue];' or any(r['statement']!='reg->nreg_cap += capval * len;' for r in selected[1:]):
        raise ValueError('pinned area and five perimeter sites required')
    for row, direction in zip(selected, [-1,0,2,1,8,4]):
        site='ExtBasic.c:'+str(row['line'])
        statement=row['statement'][:-1]
        old=f'OPENPLL_GROUND_ADD(reg, {statement}, "{site}");'
        if text.count(old)!=1:raise ValueError('one unchanged native mutation required')
        kind='area' if direction==-1 else ('diagonal_length' if direction==0 else 'edge_length')
        neighbor='tp' if direction>0 else 'NULL'
        other='tres' if direction>=0 else '-1'
        measure='area' if direction==-1 else 'len'
        coefficient='ExtCurStyle->exts_areaCap[residue]' if direction==-1 else 'capval'
        call=f'openpllGroundSupport(reg, tile, {neighbor}, extNodeClipArea, tilePlaneNum, residue, {other}, {direction}, "{site}", "{kind}", (double){measure}, (double){coefficient});'
        text=text.replace(old,'do { '+call+' '+old+' } while (0);')
    marker='#include "extract/extractInt.h"'
    if text.count(marker)!=1:raise ValueError('one declaration anchor required')
    changed['ExtBasic.c']=text.replace(marker,marker+'\n'+DECLARATION)
    changed['ExtCouple.c']+=IMPLEMENTATION
    return changed,inventory
