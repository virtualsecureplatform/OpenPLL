#!/usr/bin/env python3
"""Add isolated opt-in local charge-kernel diagnostics without numerical edits."""
from pathlib import Path
import subprocess
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT, sha, save


HEADER = r'''
#ifndef OPENPLL_CHARGE_TRACE_H
#define OPENPLL_CHARGE_TRACE_H
void OpenPLLKernelOpen(const char *);
void OpenPLLKernelClose(unsigned long);
unsigned long OpenPLLKernelBegin(const char *, const Rect *, const Rect *, int);
void OpenPLLKernelRect(unsigned long, const char *, int, const Rect *, int, unsigned int);
void OpenPLLKernelValues(unsigned long, const char *, int, double, double, double, double, double, double, double, double);
void OpenPLLKernelUse(unsigned long, const char *);
void OpenPLLKernelEvent(unsigned long, char);
#ifdef OPENPLL_CHARGE_TRACE_IMPLEMENTATION
static FILE *OpenPLLKernelFile = NULL;
static unsigned long OpenPLLKernelCount = 0, OpenPLLKernelCurrent = 0;
static const char *OpenPLLKernelComponent = "MISSING";
void OpenPLLKernelOpen(const char *cell)
{
    const char *path = getenv("OPENPLL_CAP_KERNEL_FILE");
    OpenPLLKernelCount = OpenPLLKernelCurrent = 0;
    OpenPLLKernelComponent = "MISSING";
    if (!path) return;
    if (OpenPLLKernelFile) { fprintf(stderr, "kernel stream already open\n"); exit(2); }
    OpenPLLKernelFile = fopen(path, "wx");
    if (!OpenPLLKernelFile) { perror("OPENPLL_CAP_KERNEL_FILE"); exit(2); }
    fprintf(OpenPLLKernelFile, "BEGIN \"%s\"\n", cell);
}
void OpenPLLKernelRect(unsigned long id, const char *tag, int rule, const Rect *r, int split, unsigned int dinfo)
{
    if (!id || !OpenPLLKernelFile || !r) return;
    fprintf(OpenPLLKernelFile, "RECT %lu %s %d %d %u %d %d %d %d\n", id, tag, rule, split, dinfo,
        r->r_xbot, r->r_ybot, r->r_xtop, r->r_ytop);
}
unsigned long OpenPLLKernelBegin(const char *kind, const Rect *a, const Rect *b, int direction)
{
    unsigned long id;
    if (!OpenPLLKernelFile) return 0;
    id = ++OpenPLLKernelCount;
    fprintf(OpenPLLKernelFile, "KERNEL %lu %s %d\n", id, kind, direction);
    OpenPLLKernelRect(id, "BASE_A", 0, a, 0, 0);
    OpenPLLKernelRect(id, "BASE_B", 0, b, 0, 0);
    return id;
}
void OpenPLLKernelValues(unsigned long id, const char *tag, int rule,
    double a, double b, double c, double d, double e, double f, double g, double h)
{
    if (!id || !OpenPLLKernelFile) return;
    fprintf(OpenPLLKernelFile, "VALUE %lu %s %d %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g\n",
        id, tag, rule, a, b, c, d, e, f, g, h);
}
void OpenPLLKernelUse(unsigned long id, const char *component)
{
    OpenPLLKernelCurrent = id;
    OpenPLLKernelComponent = component;
}
void OpenPLLKernelEvent(unsigned long serial, char kind)
{
    if (OpenPLLKernelFile)
        fprintf(OpenPLLKernelFile, "EVENT %lu %c %lu %s\n", serial, kind, OpenPLLKernelCurrent, OpenPLLKernelComponent);
    OpenPLLKernelCurrent = 0;
    OpenPLLKernelComponent = "MISSING";
}
void OpenPLLKernelClose(unsigned long events)
{
    if (!OpenPLLKernelFile) return;
    fprintf(OpenPLLKernelFile, "END %lu %lu\n", events, OpenPLLKernelCount);
    if (fclose(OpenPLLKernelFile) != 0) { perror("kernel stream close"); exit(2); }
    OpenPLLKernelFile = NULL;
}
#endif
#endif
'''

EDGE_HELPER = r'''
void
OpenPLLTraceGroundEdge(NodeRegion *node, CapValue delta, Tile *tile, Tile *neighbor,
        int side, const Rect *clip, int len, CapValue density,
        int plane, int raw_type, int residue, TileType dinfo)
{
    Rect edge, original;
    unsigned long id;
    if (!OpenPLLTraceEnabled || delta == 0.0) return;
    TITORECT(tile, &original);
    edge = original;
    if (side == 0 || side == 2) {
        edge.r_ybot = edge.r_ytop = (side == 0) ? TOP(tile) : BOTTOM(tile);
        edge.r_xbot = MAX(LEFT(tile), LEFT(neighbor));
        edge.r_xtop = MIN(RIGHT(tile), RIGHT(neighbor));
    } else if (side == 1 || side == 3) {
        edge.r_xbot = edge.r_xtop = (side == 1) ? LEFT(tile) : RIGHT(tile);
        edge.r_ybot = MAX(BOTTOM(tile), BOTTOM(neighbor));
        edge.r_ytop = MIN(TOP(tile), TOP(neighbor));
    }
    if (clip) GEOCLIP(&edge, clip);
    id = OpenPLLKernelBegin((side == 4) ? "DIAGONAL_EDGE" : "EDGE", &edge, NULL, side);
    OpenPLLKernelRect(id, "TILE", 0, &original, IsSplit(tile) ? 1 : 0, dinfo);
    OpenPLLKernelValues(id, "EDGE_DENSITY", 0, len, density, 0, 0, 0, 0, 0, 0);
    OpenPLLKernelUse(id, "EDGE_GROUND");
    OpenPLLTraceSurfaceContext(plane, raw_type, residue, -1, -1, -1);
    OpenPLLTraceGround(node, delta, &original, "tile_perimeter");
}
'''


def replace_once(text, before, after, count=1):
    assert text.count(before) == count, (before[:120], text.count(before), count)
    return text.replace(before, after)


def main():
    base = ROOT/'build/timing400/release_001'
    prep = base/'magic_C_kernel_source_preparation_001/assessment.json'
    assert verify(prep)['all_11_diagnostic_source_files_reproduced']
    source = ROOT/'build/timing400/magic_C_kernel_source_001'
    basic_path, couple_path = source/'extract/ExtBasic.c', source/'extract/ExtCouple.c'
    basic, couple = basic_path.read_text(), couple_path.read_text()
    basic = replace_once(basic, 'FILE *OpenPLLTraceFile = NULL;', 'FILE *OpenPLLTraceFile = NULL;\n#define OPENPLL_CHARGE_TRACE_IMPLEMENTATION\n#include "OpenPLLChargeTrace.h"')
    basic = replace_once(basic, '    OpenPLLSurfaceEvent = 0;', '    OpenPLLSurfaceEvent = 0;\n    OpenPLLKernelOpen(cell);')
    basic = replace_once(basic, '    OpenPLLSurfaceEvent++;', '    OpenPLLSurfaceEvent++;\n    OpenPLLKernelEvent(OpenPLLSurfaceEvent, kind);')
    basic = replace_once(basic, '    if (!OpenPLLSurfaceFile) return;', '    OpenPLLKernelClose(OpenPLLSurfaceEvent);\n    if (!OpenPLLSurfaceFile) return;')
    marker = '    if (getenv("OPENPLL_CAP_SURFACE_FILE") && !OpenPLLTraceEnabled)'
    basic = replace_once(basic, marker, '    if (getenv("OPENPLL_CAP_KERNEL_FILE") && !OpenPLLTraceEnabled)\n    { fprintf(stderr, "kernel trace requires contribution tracing\\n"); exit(2); }\n'+marker)
    marker = 'void\nOpenPLLTraceGroundTile('
    basic = replace_once(basic, marker, EDGE_HELPER+'\n'+marker)
    marker = '    TITORECT(tile, &support);\n    OpenPLLTraceSurfaceContext(plane, raw_type, residue, -1, -1, -1);'
    basic = replace_once(basic, marker, '''    TITORECT(tile, &support);
    {
        Rect local = support;
        unsigned long id;
        if (openpll_clip) GEOCLIP(&local, openpll_clip);
        id = OpenPLLKernelBegin("AREA", &local, NULL, -1);
        OpenPLLKernelRect(id, "TILE", 0, &support, IsSplit(tile) ? 1 : 0, openpll_dinfo);
        OpenPLLKernelValues(id, "AREA_DENSITY", 0, openpll_area, openpll_density, 0, 0, 0, 0, 0, 0);
        OpenPLLKernelUse(id, "AREA_GROUND");
    }
    OpenPLLTraceSurfaceContext(plane, raw_type, residue, -1, -1, -1);''')
    basic = replace_once(basic, 'const char *reason, int plane, int raw_type, int residue)',
        'const char *reason, int plane, int raw_type, int residue,\n        TileType openpll_dinfo, const Rect *openpll_clip, dlong openpll_area, CapValue openpll_density)')
    marker = 'tile, "tile_area", tilePlaneNum, type, residue);'
    basic = replace_once(basic, marker, 'tile, "tile_area", tilePlaneNum, type, residue, dinfo, extNodeClipArea, area, ExtCurStyle->exts_areaCap[residue]);')
    marker = 'OpenPLLTraceGroundTile(reg, reg->nreg_cap - openpll_before, tile, "tile_perimeter", tilePlaneNum, type, residue);'
    assert basic.count(marker) == 5
    for side in [4, 0, 1, 2, 3]:
        neighbor = 'tile' if side == 4 else 'tp'
        basic = basic.replace(marker, f'OpenPLLTraceGroundEdge(reg, reg->nreg_cap - openpll_before, tile, {neighbor}, {side}, extNodeClipArea, len, capval, tilePlaneNum, type, residue, dinfo);', 1)
    marker = '    if (!OpenPLLTraceEnabled || delta == 0.0) return;\n    fprintf(OpenPLLTraceFile, "OPENPLL_G'
    assert basic.count(marker) == 1
    basic = basic.replace(marker, '''    if (!OpenPLLTraceEnabled || delta == 0.0) return;
    if (strcmp(reason, "output_zero_clamp") == 0)
        OpenPLLKernelUse(OpenPLLKernelBegin("ROUNDING", NULL, NULL, -1), "NODE_ROUNDING");
    fprintf(OpenPLLTraceFile, "OPENPLL_G''')
    couple = replace_once(couple, 'extern int OpenPLLTraceEnabled;', 'extern int OpenPLLTraceEnabled;\n#include "OpenPLLChargeTrace.h"')
    couple = replace_once(couple, 'struct overlap\n{', 'struct overlap\n{\n    unsigned long openpll_kernel;\n    int openpll_rule;')
    couple = replace_once(couple, 'struct sideoverlap\n{', 'struct sideoverlap\n{\n    unsigned long openpll_kernel;\n    int openpll_rule;')
    marker = '    if ((ov.o_pmask = ExtCurStyle->exts_overlapShieldPlanes[ta][tb]))'
    couple = replace_once(couple, marker, '''    ov.openpll_kernel = OpenPLLKernelBegin("OVERLAP", &ov.o_clip, &ov.o_clip, -1);
    ov.openpll_rule = 0;
    OpenPLLKernelValues(ov.openpll_kernel, "OVERLAP_BASE", 0, ov.o_area,
        ExtCurStyle->exts_areaCap[ta], ExtCurStyle->exts_overlapCap[ta][tb],
        IsSplit(tabove) ? 1 : 0, IsSplit(tbelow) ? 1 : 0, ecpls->dinfo, dinfo, 0);
'''+marker)
    marker = '    /* If any capacitance remains, add this record to the table */'
    couple = replace_once(couple, marker, '    OpenPLLKernelValues(ov.openpll_kernel, "OVERLAP_REMAINING", 0, ov.o_area, 0, 0, 0, 0, 0, 0, 0);\n'+marker)
    marker = '    if (area > 0)\n\tov->o_area -= area;'
    couple = replace_once(couple, marker, '''    if (area > 0) {
        OpenPLLKernelRect(ov->openpll_kernel, "AREA_SHIELD", ov->openpll_rule, &r, IsSplit(tile) ? 1 : 0, dinfo);
        OpenPLLKernelValues(ov->openpll_kernel, "AREA_SHIELD_SIZE", ov->openpll_rule, area, 0, 0, 0, 0, 0, 0, 0);
        ov->o_area -= area;
    }''')
    marker = '\tov->o_area -= area;\n\treturn (0);'
    couple = replace_once(couple, marker, '''        OpenPLLKernelRect(ov->openpll_kernel, "AREA_SHIELD", ov->openpll_rule, &r, IsSplit(tile) ? 1 : 0, dinfo);
        OpenPLLKernelValues(ov->openpll_kernel, "AREA_SHIELD_SIZE", ov->openpll_rule, area, 0, 0, 0, 0, 0, 0, 0);
'''+marker)
    # Each final update explicitly binds to its owning local kernel.
    for reason, expression, kid, component in [
        ('overlap_shield', 'OpenPLLTraceGround(rabove', 'ov.openpll_kernel', 'OVERLAP_GROUND'),
        ('parallel_overlap', 'OpenPLLTracePair(rabove', 'ov.openpll_kernel', 'OVERLAP_PAIR'),
    ]:
        marker = expression
        assert couple.count(marker) == 1
        couple = couple.replace(marker, f'OpenPLLKernelUse({kid}, "{component}"); '+marker)
    # Halo and legacy local kernels. Helpers receive native values unchanged.
    marker = '    cap = subcap = (CapValue) 0;'
    couple = replace_once(couple, marker, '''    sov.openpll_kernel = OpenPLLKernelBegin("FRINGE_HALO", &bp->b_segment, &sov.so_clip, bp->b_direction);
    sov.openpll_rule = 0;
    OpenPLLKernelValues(sov.openpll_kernel, "FRINGE_BASE", 0, length, dnear, dfar,
        ExtCurStyle->exts_overlapMult[ta][tb], ExtCurStyle->exts_overlapMult[ta][0], cfrac, sfrac, IsSplit(tp) ? 1 : 0);
'''+marker)
    marker = '    areaAccountedFor = 0;'
    couple = replace_once(couple, marker, marker+'''
    ov.openpll_kernel = OpenPLLKernelBegin("FRINGE_LEGACY", &bp->b_segment, &ov.o_clip, bp->b_direction);
    ov.openpll_rule = 0;
    OpenPLLKernelValues(ov.openpll_kernel, "LEGACY_BASE", 0, length, areaTotal, IsSplit(tp) ? 1 : 0, 0, 0, 0, 0, 0);
''')
    marker = '    sov->so_coupfrac += (sfar - snear) * ((double)length / (double)sov->so_length);'
    couple = replace_once(couple, marker, marker+'''
    OpenPLLKernelRect(sov->openpll_kernel, "FRINGE_SHIELD", sov->openpll_rule, &r, IsSplit(tile) ? 1 : 0, dinfo);
    OpenPLLKernelValues(sov->openpll_kernel, "FRINGE_SHIELD_GEOMETRY", sov->openpll_rule,
        length, sov->so_length, dnear, dfar, ExtCurStyle->exts_overlapMult[ta][tb], ExtCurStyle->exts_overlapMult[ta][0], 0, 0);
''')
    marker = '\t    sov.so_pmask = ExtCurStyle->exts_sideOverlapShieldPlanes[ta][tb];'
    couple = replace_once(couple, marker, '''            sov.openpll_rule++;
            OpenPLLKernelValues(sov.openpll_kernel, "HALO_RULE", sov.openpll_rule, e->ec_cap, 0, 0, 0, 0, 0, 0, 0);
'''+marker)
    marker = '\t    if (rtp != rbp)\n\t    {\n\t\tefflength = (cfrac - sov.so_coupfrac)'
    couple = replace_once(couple, marker, '''            OpenPLLKernelValues(sov.openpll_kernel, "HALO_RULE_REMAINING", sov.openpll_rule,
                sov.so_coupfrac, sov.so_subfrac, (rtp != rbp) ? 1 : 0, 0, 0, 0, 0, 0);
'''+marker)
    marker = '\t    ov.o_area = areaTotal;'
    couple = replace_once(couple, marker, '''            ov.openpll_rule++;
            OpenPLLKernelValues(ov.openpll_kernel, "LEGACY_RULE", ov.openpll_rule, e->ec_cap, areaTotal, 0, 0, 0, 0, 0, 0);
'''+marker)
    marker = '\t    if (rtp != rbp)\n\t\tcap += e->ec_cap * ov.o_area;'
    couple = replace_once(couple, marker, '''            OpenPLLKernelValues(ov.openpll_kernel, "LEGACY_RULE_REMAINING", ov.openpll_rule,
                ov.o_area, (rtp != rbp) ? 1 : 0, 0, 0, 0, 0, 0, 0);
'''+marker)
    marker = '    if (OpenPLLTraceEnabled) { OpenPLLTraceSurfaceContext(esws->plane_of_boundary, TiGetTypeExact(bp->b_inside), ta, -1, -1, -1); OpenPLLTraceGround(rbp, rbp->nreg_cap - openpll_before, &bp->b_segment, "fringe_shield_with_roundoff"); }'
    assert couple.count(marker) == 2
    halo = '''    if (OpenPLLTraceEnabled) {
        OpenPLLKernelValues(sov.openpll_kernel, "GROUND_PHYSICAL", 0, subcap, length, sfrac, subfrac,
            ExtCurStyle->exts_perimCap[ta][0], 0, 0, 0);
        OpenPLLKernelUse(sov.openpll_kernel, "FRINGE_GROUND");
'''+marker[len('    if (OpenPLLTraceEnabled) {'):]
    legacy = '''    if (OpenPLLTraceEnabled) {
        OpenPLLKernelValues(ov.openpll_kernel, "GROUND_PHYSICAL", 0, subcap, length, areaAccountedFor, areaTotal,
            ExtCurStyle->exts_perimCap[ta][outtype], 0, 0, 0);
        OpenPLLKernelUse(ov.openpll_kernel, "FRINGE_GROUND");
'''+marker[len('    if (OpenPLLTraceEnabled) {'):]
    couple = couple.replace(marker, halo, 1).replace(marker, legacy, 1)
    marker = 'OpenPLLTracePair(rbp, rtp, extGetCapValue(he) - openpll_before, &bp->b_segment, &openpll_target, "edge_fringe");'
    assert couple.count(marker) == 2
    couple = couple.replace(marker, 'OpenPLLKernelValues(sov.openpll_kernel, "PAIR_PHYSICAL", 0, cap, 0, 0, 0, 0, 0, 0, 0); OpenPLLKernelUse(sov.openpll_kernel, "FRINGE_PAIR"); '+marker, 1)
    couple = couple.replace(marker, 'OpenPLLKernelValues(ov.openpll_kernel, "PAIR_PHYSICAL", 0, cap, 0, 0, 0, 0, 0, 0, 0); OpenPLLKernelUse(ov.openpll_kernel, "FRINGE_PAIR"); '+marker, 1) if couple.count(marker) == 1 else couple
    # The first replacement retains the marker text; replace the second occurrence explicitly.
    wrong = 'OpenPLLKernelValues(sov.openpll_kernel, "PAIR_PHYSICAL", 0, cap, 0, 0, 0, 0, 0, 0, 0); OpenPLLKernelUse(sov.openpll_kernel, "FRINGE_PAIR"); '+marker
    assert couple.count(wrong) == 1
    prefix, suffix = couple.split(wrong, 1)
    assert suffix.count(marker) == 1
    suffix = suffix.replace(marker, 'OpenPLLKernelValues(ov.openpll_kernel, "PAIR_PHYSICAL", 0, cap, 0, 0, 0, 0, 0, 0, 0); OpenPLLKernelUse(ov.openpll_kernel, "FRINGE_PAIR"); '+marker)
    couple = prefix+wrong+suffix
    marker = '    if (OpenPLLTraceEnabled) { OpenPLLTraceSurfaceContext(esws->plane_of_boundary, TiGetTypeExact(bp->b_inside), ta, -1, -1, -1); OpenPLLTraceGround(rbp, rbp->nreg_cap - openpll_before, &bp->b_segment, "fringe_blocked_substrate"); }'
    couple = replace_once(couple, marker, '''    if (OpenPLLTraceEnabled) {
        unsigned long id = OpenPLLKernelBegin("BLOCKED_FRINGE", &bp->b_segment, clip, bp->b_direction);
        OpenPLLKernelValues(id, "BLOCKED_BASE", 0, length, dnear, mult, snear,
            ExtCurStyle->exts_perimCap[ta][tb], subcap, 0, 0);
        OpenPLLKernelUse(id, "BLOCKED_GROUND");
'''+marker[len('    if (OpenPLLTraceEnabled) {'):])
    # Sidewall source/target edges must use the exact interval selected by the caller.
    marker = 'overlap, sep, esws->extCoupleList, bp->b_inside, esws->plane_of_boundary);'
    couple = replace_once(couple, marker, 'overlap, sep, esws->extCoupleList, bp->b_inside, esws->plane_of_boundary, &bp->b_segment);', 4)
    couple = replace_once(couple, 'extCoupleList, openpll_origin, openpll_plane)', 'extCoupleList, openpll_origin, openpll_plane, openpll_boundary)')
    couple = replace_once(couple, '    int openpll_plane;', '    int openpll_plane;\n    const Rect *openpll_boundary;')
    marker = '    /* Get the tile types of tpnear and tpfar */'
    couple = replace_once(couple, marker, '''    unsigned long openpll_id;
    Rect openpll_edge_a = *openpll_boundary, openpll_edge_b = *openpll_boundary;
    int openpll_lo, openpll_hi, openpll_rule = 0;
    if (bdir == BD_TOP || bdir == BD_BOTTOM) {
        openpll_lo = MAX(openpll_boundary->r_xbot, MAX(LEFT(tpnear), LEFT(tpfar)));
        openpll_hi = MIN(openpll_boundary->r_xtop, MIN(RIGHT(tpnear), RIGHT(tpfar)));
        openpll_edge_a.r_xbot = openpll_edge_b.r_xbot = openpll_lo;
        openpll_edge_a.r_xtop = openpll_edge_b.r_xtop = openpll_hi;
        openpll_edge_b.r_ybot = openpll_edge_b.r_ytop = (bdir == BD_TOP) ? BOTTOM(tpfar) : TOP(tpfar);
    } else {
        openpll_lo = MAX(openpll_boundary->r_ybot, MAX(BOTTOM(tpnear), BOTTOM(tpfar)));
        openpll_hi = MIN(openpll_boundary->r_ytop, MIN(TOP(tpnear), TOP(tpfar)));
        openpll_edge_a.r_ybot = openpll_edge_b.r_ybot = openpll_lo;
        openpll_edge_a.r_ytop = openpll_edge_b.r_ytop = openpll_hi;
        openpll_edge_b.r_xbot = openpll_edge_b.r_xtop = (bdir == BD_LEFT) ? RIGHT(tpfar) : LEFT(tpfar);
    }
    openpll_id = OpenPLLKernelBegin("SIDEWALL", &openpll_edge_a, &openpll_edge_b, bdir);
    OpenPLLKernelValues(openpll_id, "SIDEWALL_BASE", 0, overlap, sep, openpll_hi-openpll_lo, 0, 0, 0, 0, 0);
'''+marker)
    marker = '\t    cap += (e->ec_cap * overlap) / (sep + e->ec_offset);'
    couple = replace_once(couple, marker, '''            OpenPLLKernelValues(openpll_id, "SIDEWALL_RULE", ++openpll_rule, e->ec_cap, e->ec_offset, 0, 0, 0, 0, 0, 0);
'''+marker)
    marker = 'OpenPLLTracePair(rinside, rfar, extGetCapValue(he) - openpll_before, &openpll_a, &openpll_b, "sidewall");'
    couple = replace_once(couple, marker, 'OpenPLLKernelUse(openpll_id, "SIDEWALL_PAIR"); '+marker)
    out = base/'magic_C_kernel_trace_patch_001'
    out.mkdir(exist_ok=False)
    basic_path.write_text(basic)
    couple_path.write_text(couple)
    header = source/'extract/OpenPLLChargeTrace.h'
    header.write_text(HEADER)
    subprocess.run(['git', '-C', str(source), 'add', '-N', str(header)], check=True)
    patch = subprocess.check_output(['git', '-C', str(source), 'diff', '--binary'])
    (out/'change.patch').write_bytes(patch)
    files = subprocess.check_output(['git', '-C', str(source), 'diff', '--name-only'], text=True).splitlines()
    for name in files:
        (out/('patched_'+Path(name).name)).write_bytes((source/name).read_bytes())
    save(out/'assessment.json', dict(input_sha256={str(p): sha(p) for p in [Path(__file__).resolve(), prep]},
        artifacts={str(p): sha(p) for p in out.iterdir()},
        diagnostic_source_files={str(source/f): sha(source/f) for f in files},
        source_tree_isolated_from_previous_pinned_sources=True,
        ordered_charge_kernel_trace_prepared=True, native_numerical_equivalence_controls_passed=False,
        local_charge_kernel_completeness_qualified=False, release_qualified=False, adopted=False))
    print('Prepared isolated local charge-kernel instrumentation; compile and native controls required.')


if __name__ == '__main__':
    main()
