"""Native diagnostic only: report invalid breakpoint bounds and raw negative area."""
def transform_make(text):
    for axis,lo,hi in [('x','LEFT','RIGHT'),('y','BOTTOM','TOP')]:
        marker=('\n    p2= info->breakList;' if axis=='x' else '\n    p2 = info->breakList;')
        if text.count(marker)!=1:raise ValueError('unique axis breakpoint list required')
        diagnostic='''
    if (getenv("OPENPLL_RC_AREA_DIAGNOSTIC") != NULL)
    {
        Breakpoint *bp;
        for (bp = info->breakList; bp != NULL; bp = bp->br_next)
            if (bp->br_loc.p_AXIS < LO(tile) || bp->br_loc.p_AXIS > HI(tile))
                TxError("OPENPLL_RC_BREAK_BOUNDS net=%s axis=AXIS tile=%d,%d,%d,%d break=%d,%d node=%d,%d\\n",
                    ResCurrentNode, LEFT(tile), BOTTOM(tile), RIGHT(tile), TOP(tile),
                    bp->br_loc.p_x, bp->br_loc.p_y,
                    bp->br_this->rn_loc.p_x, bp->br_this->rn_loc.p_y);
    }
'''.replace('AXIS',axis).replace('LO(tile)',lo+'(tile)').replace('HI(tile)',hi+'(tile)')
        text=text.replace(marker,marker+diagnostic)
    return text

def transform_simple(text):
    marker='\ttotalarea += workingNode->rn_float.rn_area;'
    if text.count(marker)!=1:raise ValueError('unique native raw area summation required')
    diagnostic='''
        if (getenv("OPENPLL_RC_AREA_DIAGNOSTIC") != NULL && workingNode->rn_float.rn_area < 0)
            TxError("OPENPLL_RC_NEGATIVE_AREA net=%s node=%d,%d area=%g totalcap=%g\\n",
                ResCurrentNode, workingNode->rn_loc.p_x, workingNode->rn_loc.p_y,
                workingNode->rn_float.rn_area, totalcap);
'''
    return text.replace(marker,diagnostic+marker)
