"""Use actual cross-plane overlap points and avoid integer overflow in tile areas."""
def transform_basic(text):
    for call in ['ResNewSDDevice','ResNewSubDevice']:
        before='    xj = (LEFT(tile) + RIGHT(tile)) / 2;\n    yj = (TOP(tile) + BOTTOM(tile)) / 2;\n    '+call+'(tp, tile, xj, yj, OTHERPLANE, &ResNodeQueue);'
        after='''    /* Both terminal and conductor tiles must contain the breakpoint. */
    {
        int lx = MAX(LEFT(tile), LEFT(tp)), hx = MIN(RIGHT(tile), RIGHT(tp));
        int ly = MAX(BOTTOM(tile), BOTTOM(tp)), hy = MIN(TOP(tile), TOP(tp));
        if (lx >= hx || ly >= hy)
        {TxError("OPENPLL_RC_EMPTY_CROSSPLANE_OVERLAP\\n"); return 0;}
        xj = lx + (hx - lx) / 2;
        yj = ly + (hy - ly) / 2;
    }
    CALL(tp, tile, xj, yj, OTHERPLANE, &ResNodeQueue);'''.replace('CALL',call)
        if text.count(before)!=1:raise ValueError('one original cross-plane '+call+' center required')
        text=text.replace(before,after)
    return text

def transform_make(text):
    changes=[
      ('p1->br_this->rn_float.rn_area += height * (RIGHT(tile) - LEFT(tile));','height','(RIGHT(tile) - LEFT(tile))','p1->br_this->rn_float.rn_area += (double)height * (RIGHT(tile) - LEFT(tile));'),
      ('p2->br_this->rn_float.rn_area += height * (p2->br_loc.p_x - LEFT(tile));','height','(p2->br_loc.p_x - LEFT(tile))','p2->br_this->rn_float.rn_area += (double)height * (p2->br_loc.p_x - LEFT(tile));'),
      ('rArea = ((p2->br_loc.p_x - p1->br_loc.p_x) * height) / 2;','height','(p2->br_loc.p_x - p1->br_loc.p_x)','rArea = ((double)(p2->br_loc.p_x - p1->br_loc.p_x) * height) / 2.0;'),
      ('p2->br_this->rn_float.rn_area += height * (RIGHT(tile) - p2->br_loc.p_x);','height','(RIGHT(tile) - p2->br_loc.p_x)','p2->br_this->rn_float.rn_area += (double)height * (RIGHT(tile) - p2->br_loc.p_x);'),
      ('p1->br_this->rn_float.rn_area += width * (TOP(tile) - BOTTOM(tile));','width','(TOP(tile) - BOTTOM(tile))','p1->br_this->rn_float.rn_area += (double)width * (TOP(tile) - BOTTOM(tile));'),
      ('p2->br_this->rn_float.rn_area += width * (p2->br_loc.p_y - BOTTOM(tile));','width','(p2->br_loc.p_y - BOTTOM(tile))','p2->br_this->rn_float.rn_area += (double)width * (p2->br_loc.p_y - BOTTOM(tile));'),
      ('rArea = ((p2->br_loc.p_y - p1->br_loc.p_y) * width) / 2;','width','(p2->br_loc.p_y - p1->br_loc.p_y)','rArea = ((double)(p2->br_loc.p_y - p1->br_loc.p_y) * width) / 2.0;'),
      ('p2->br_this->rn_float.rn_area += width * (TOP(tile) - p2->br_loc.p_y);','width','(TOP(tile) - p2->br_loc.p_y)','p2->br_this->rn_float.rn_area += (double)width * (TOP(tile) - p2->br_loc.p_y);')]
    for before,a,b,after in changes:
        if text.count(before)!=1:raise ValueError('one pinned tile-area expression required: '+before)
        diagnostic='''{
        long long product = (long long)(A) * (B);
        if (getenv("OPENPLL_RC_AREA_DIAGNOSTIC") != NULL &&
            (product > 2147483647LL || product < -2147483648LL))
            TxError("OPENPLL_RC_WIDENED_AREA_PRODUCT net=%s operands=%d,%d product=%lld\\n",
                ResCurrentNode, A, B, product);
    }
    '''.replace('A',a).replace('B',b)
        # Substitute only placeholders, not letters in diagnostic identifiers.
        diagnostic='''{
        long long product = (long long)(FACTOR_A) * (FACTOR_B);
        if (getenv("OPENPLL_RC_AREA_DIAGNOSTIC") != NULL &&
            (product > 2147483647LL || product < -2147483648LL))
            TxError("OPENPLL_RC_WIDENED_AREA_PRODUCT net=%s operands=%d,%d product=%lld\\n",
                ResCurrentNode, FACTOR_A, FACTOR_B, product);
    }
    '''.replace('FACTOR_A',a).replace('FACTOR_B',b)
        text=text.replace(before,diagnostic+after)
    return text
