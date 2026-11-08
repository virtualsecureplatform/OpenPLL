"""Log overlap base support and leaf shielding rectangles without changing math."""
from instrument_ground_lifecycle import instrument_sources


def instrument_with_shielding(sources):
    changed, inventory = instrument_sources(sources)
    text = changed['ExtCouple.c']
    def replace(old, new, count=1):
        nonlocal text
        if text.count(old) != count:
            raise ValueError('pinned overlap source differs: ' + old[:80])
        text = text.replace(old, new)
    replace('#include "coupling_geometry_trace.h"', '#include "coupling_geometry_trace.h"\n#include "overlap_shielding_trace.h"')
    marker = '    if ((ov.o_pmask = ExtCurStyle->exts_overlapShieldPlanes[ta][tb]))'
    replace(marker, '''    openpllOverlapId++;
    openpllOverlapSupport("overlap_support_begin", rabove, rbelow,
        &ov.o_clip, ov.o_area, ecpls->plane_of_tile, ecpls->plane_checked,
        IsSplit(tabove) || IsSplit(tbelow), 0, 0,
        (double)ExtCurStyle->exts_overlapCap[ta][tb]);
''' + marker)
    marker = '    /* If any capacitance remains, add this record to the table */\n    if (ov.o_area > 0)'
    replace(marker, '''    openpllOverlapSupport("overlap_support_end", rabove, rbelow,
        &ov.o_clip, ov.o_area, ecpls->plane_of_tile, ecpls->plane_checked,
        IsSplit(tabove) || IsSplit(tbelow), 0, 0,
        (double)ExtCurStyle->exts_overlapCap[ta][tb]);
''' + marker)
    # Both terminal callbacks subtract one native clipped area. Intermediate
    # callbacks recurse; logging their rectangles too would double count.
    replace('ov->o_area -= area;', '''{
            ov->o_area -= area;
            openpllOverlapSupport("overlap_shield_leaf", NULL, NULL, &r,
                area, -1, -1, IsSplit(tile), SplitDirection(tile),
                (dinfo & TT_SIDE) ? 1 : 0, 0.0);
        }''', 2)
    changed['ExtCouple.c'] = text
    return changed, inventory
