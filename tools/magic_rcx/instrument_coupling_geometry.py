"""Insert logging into the four native flat coupling update paths."""
def instrument(text):
    def replace(old,new,count=1):
        nonlocal text
        if text.count(old)!=count:raise ValueError('pinned coupling source layout differs: '+old[:60])
        text=text.replace(old,new)
    replace('/* --------------------- Debugging stuff ---------------------- */','#include "coupling_geometry_trace.h"\n\n/* --------------------- Debugging stuff ---------------------- */')
    replace('    ecs.def = def;','    ecs.def = def;\n    openpllTraceCell = def->cd_name;\n    openpllTraceEpoch++;')
    replace('extBasicCouple, (ClientData) &ecs);\n    }\n\n}', 'extBasicCouple, (ClientData) &ecs);\n    }\n    if (openpllTraceFile) fflush(openpllTraceFile);\n\n}')
    replace(r'fprintf(outFile, "cap \"%s\" ", text);', r'fprintf(outFile, "cap \"%s\" ", text);'+'\n        openpllTraceNodeName(ck->ck_1, text);')
    replace(r'fprintf(outFile, "\"%s\" %lg\n", text, cap);', r'fprintf(outFile, "\"%s\" %lg\n", text, cap);'+'\n        openpllTraceNodeName(ck->ck_2, text);')
    replace('c += ExtCurStyle->exts_overlapCap[ta][tb] * ov.o_area;', 'c += ExtCurStyle->exts_overlapCap[ta][tb] * ov.o_area;\n        openpllTraceEvent(rabove, rbelow, ExtCurStyle->exts_overlapCap[ta][tb] * ov.o_area, "overlap", ecpls->plane_of_tile, ecpls->plane_checked, &ov.o_clip, &ov.o_clip, -1, ov.o_area, 0);')
    # The halo and legacy paths have identical update statements but different support structures.
    anchor='\tif (CAP_DEBUG) extAdjustCouple(he, cap, "sideoverlap");'
    if text.count(anchor)!=2:raise ValueError('two side-overlap update sites required')
    pos=text.index(anchor);text=text[:pos]+'        openpllTraceEvent(rbp, rtp, cap, "sideoverlap_halo", esws->plane_of_boundary, esws->plane_checked, &bp->b_segment, &sov.so_clip, bp->b_direction, length, 0);\n'+text[pos:]
    pos=text.index(anchor,text.index(anchor)+len(anchor));text=text[:pos]+'        openpllTraceEvent(rbp, rtp, cap, "sideoverlap_legacy", esws->plane_of_boundary, esws->plane_checked, &bp->b_segment, &ov.o_clip, bp->b_direction, length, 0);\n'+text[pos:]
    replace('overlap, sep, esws->extCoupleList);','overlap, sep, esws->extCoupleList, bp, esws->plane_of_boundary);',4)
    replace('extSideCommon(rinside, rfar, tpnear, tpfar, bdir, overlap, sep, extCoupleList)','extSideCommon(rinside, rfar, tpnear, tpfar, bdir, overlap, sep, extCoupleList, bp, plane)')
    # New K&R arguments must be declared before the function body.
    replace('    EdgeCap  *extCoupleList;\t/* List of sidewall capacitance rules */\n{','    EdgeCap  *extCoupleList;\t/* List of sidewall capacitance rules */\n    Boundary *bp;\n    int plane;\n{')
    replace('    TileType near, far;','    TileType near, far;\n    Rect traceNear, traceFar;\n    int low, high;')
    geometry='''    traceNear = bp->b_segment;
    traceFar = traceNear;
    if (traceNear.r_xbot == traceNear.r_xtop) {
        low = MAX(traceNear.r_ybot, MAX(BOTTOM(tpnear), BOTTOM(tpfar)));
        high = MIN(traceNear.r_ytop, MIN(TOP(tpnear), TOP(tpfar)));
        traceNear.r_ybot = traceFar.r_ybot = low;
        traceNear.r_ytop = traceFar.r_ytop = high;
        traceFar.r_xbot = traceFar.r_xtop = (bdir == BD_LEFT) ? RIGHT(tpfar) : LEFT(tpfar);
    } else {
        low = MAX(traceNear.r_xbot, MAX(LEFT(tpnear), LEFT(tpfar)));
        high = MIN(traceNear.r_xtop, MIN(RIGHT(tpnear), RIGHT(tpfar)));
        traceNear.r_xbot = traceFar.r_xbot = low;
        traceNear.r_xtop = traceFar.r_xtop = high;
        traceFar.r_ybot = traceFar.r_ytop = (bdir == BD_BOTTOM) ? TOP(tpfar) : BOTTOM(tpfar);
    }
'''
    replace('    cap = extGetCapValue(he);\n    for (e = extCoupleList;',geometry+'    cap = extGetCapValue(he);\n    for (e = extCoupleList;')
    replace('cap += (e->ec_cap * overlap) / (sep + e->ec_offset);','cap += (e->ec_cap * overlap) / (sep + e->ec_offset);\n            openpllTraceEvent(rinside, rfar, (e->ec_cap * overlap) / (sep + e->ec_offset), "sidewall", plane, plane, &traceNear, &traceFar, bdir, overlap, sep);')
    return text
