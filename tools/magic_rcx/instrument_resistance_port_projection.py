"""Project rectangular per-tile port attachments into their actual intersection."""
from instrument_resistance_area_signfix import instrument_sources as area_corrected

OLD = '\trp->rp_loc = node->drivepoint; \\\n'
NEW = OLD + '''\tif (!IsSplit(tile) && \\
\t    MAX(LEFT(tile), rp->rp_bbox.r_xbot) <= MIN(RIGHT(tile), rp->rp_bbox.r_xtop) && \\
\t    MAX(BOTTOM(tile), rp->rp_bbox.r_ybot) <= MIN(TOP(tile), rp->rp_bbox.r_ytop)) { \\
\t    rp->rp_loc.p_x = MAX(MAX(LEFT(tile), rp->rp_bbox.r_xbot), \\
\t        MIN(MIN(RIGHT(tile), rp->rp_bbox.r_xtop), rp->rp_loc.p_x)); \\
\t    rp->rp_loc.p_y = MAX(MAX(BOTTOM(tile), rp->rp_bbox.r_ybot), \\
\t        MIN(MIN(TOP(tile), rp->rp_bbox.r_ytop), rp->rp_loc.p_y)); \\
\t} \\
'''


def project_source(text):
    if text.count(OLD) != 1:
        raise ValueError('one pinned NEWPORT drivepoint assignment required')
    return text.replace(OLD, NEW)


def instrument_sources(sources):
    changed = area_corrected(sources)
    changed['resis.h'] = project_source(changed['resis.h'])
    return changed
