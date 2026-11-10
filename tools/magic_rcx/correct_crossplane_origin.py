"""Set a real source point when FindStartTile discovers an overlapping-plane driver."""
def transform(text):
    a=text.index('FindStartTile(resisdata, SourcePoint)');b=text.index('\n}',a)+2
    part=text[a:b];needle='if (tp != NULL) return tp;'
    if part.count(needle)!=2:raise ValueError('both native cross-plane driver returns required')
    block='''if (tp != NULL)
        {
            int lx = MAX(r.r_xbot, LEFT(tp)), hx = MIN(r.r_xtop, RIGHT(tp));
            int ly = MAX(r.r_ybot, BOTTOM(tp)), hy = MIN(r.r_ytop, TOP(tp));
            if (lx >= hx || ly >= hy)
            {TxError("OPENPLL_RC_EMPTY_DRIVER_OVERLAP\\n"); return NULL;}
            if (getenv("OPENPLL_RC_AREA_DIAGNOSTIC") != NULL &&
                (SourcePoint->p_x < LEFT(tp) || SourcePoint->p_x > RIGHT(tp) ||
                 SourcePoint->p_y < BOTTOM(tp) || SourcePoint->p_y > TOP(tp)))
                TxError("OPENPLL_RC_DRIVER_ORIGIN_CORRECTED net=%s old=%d,%d new=%d,%d\\n",
                    ResCurrentNode, SourcePoint->p_x, SourcePoint->p_y,
                    lx + (hx-lx)/2, ly + (hy-ly)/2);
            SourcePoint->p_x = lx + (hx-lx)/2;
            SourcePoint->p_y = ly + (hy-ly)/2;
            return tp;
        }'''
    return text[:a]+part.replace(needle,block)+text[b:]
