"""Add native per-rule fringe multipliers, support and shielding fractions."""
from instrument_overlap_shielding import instrument_with_shielding


def instrument_with_fringe(sources):
    changed, inventory = instrument_with_shielding(sources)
    text = changed['ExtCouple.c']
    def replace(old, new):
        nonlocal text
        if text.count(old) != 1:
            raise ValueError('pinned fringe source differs: ' + old[:80])
        text = text.replace(old, new)
    replace('#include "overlap_shielding_trace.h"', '#include "overlap_shielding_trace.h"\n#include "fringe_support_trace.h"')
    marker = '    sov.so_ctype = tb;'
    begin = '''
    openpllFringeId++;
    openpllFringeSupport("fringe_rule_begin", rbp, rtp, bp, &sov.so_clip,
        length, length, esws->plane_of_boundary, esws->plane_checked,
        (double)ExtCurStyle->exts_overlapMult[ta][tb],
        (double)ExtCurStyle->exts_overlapMult[ta][0],
        cfrac, sfrac, sov.so_coupfrac, sov.so_subfrac,
        (double)e->ec_cap, IsSplit(tp) || IsSplit(bp->b_inside));
'''
    replace(marker, marker + begin)
    marker = '\t    if (rtp != rbp)\n\t    {'
    end = begin.replace('    openpllFringeId++;\n', '').replace('fringe_rule_begin', 'fringe_rule_end')
    replace(marker, end + marker)
    marker = '    sov->so_coupfrac += (sfar - snear) * ((double)length / (double)sov->so_length);'
    leaf = '''
    openpllFringeSupport("fringe_shield_leaf", NULL, NULL, bp, &r,
        sov->so_length, length, sov->so_esws->plane_of_boundary,
        sov->so_esws->plane_checked,
        (double)ExtCurStyle->exts_overlapMult[ta][tb],
        (double)ExtCurStyle->exts_overlapMult[ta][0],
        0.0, 0.0, sov->so_coupfrac, sov->so_subfrac, 0.0, IsSplit(tile));
'''
    replace(marker, marker + leaf)
    changed['ExtCouple.c'] = text
    return changed, inventory
