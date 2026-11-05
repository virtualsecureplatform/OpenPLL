#!/usr/bin/env python3
"""Retain plane/type/residue for each unchanged native C trace contribution.

Keep the established contribution stream byte format. A separate exclusive
stream has one ordered surface record per nonzero ground/pair contribution.
No clipping, C formula, R arithmetic or native output statement is changed.
"""
import difflib
from pathlib import Path
import subprocess
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT, sha, save


HELPER = r'''
static FILE *OpenPLLSurfaceFile = NULL;
static unsigned long OpenPLLSurfaceEvent = 0;
static int OpenPLLSurfaceContext[6] = {-1, -1, -1, -1, -1, -1};

void
OpenPLLTraceSurfaceContext(int pa, int raw_a, int effective_a,
        int pb, int raw_b, int effective_b)
{
    OpenPLLSurfaceContext[0] = pa;
    OpenPLLSurfaceContext[1] = raw_a;
    OpenPLLSurfaceContext[2] = (pa >= 0 && effective_a >= 0 && DBIsContact(effective_a))
        ? DBPlaneToResidue(effective_a, pa) : effective_a;
    OpenPLLSurfaceContext[3] = pb;
    OpenPLLSurfaceContext[4] = raw_b;
    OpenPLLSurfaceContext[5] = (pb >= 0 && effective_b >= 0 && DBIsContact(effective_b))
        ? DBPlaneToResidue(effective_b, pb) : effective_b;
}

static void
OpenPLLTraceSurfaceBegin(const char *cell)
{
    const char *path = getenv("OPENPLL_CAP_SURFACE_FILE");
    int index;
    OpenPLLSurfaceEvent = 0;
    OpenPLLTraceSurfaceContext(-1, -1, -1, -1, -1, -1);
    if (!path) return;
    if (OpenPLLSurfaceFile) { fprintf(stderr, "OPENPLL surface stream already open\n"); exit(2); }
    OpenPLLSurfaceFile = fopen(path, "wx");
    if (!OpenPLLSurfaceFile) { perror("OPENPLL_CAP_SURFACE_FILE"); exit(2); }
    fprintf(OpenPLLSurfaceFile, "BEGIN \"%s\"\n", cell);
    for (index = 0; index < TT_MAXTYPES; index++)
        if (DBTypeLongName(index))
            fprintf(OpenPLLSurfaceFile, "TYPE %d \"%s\"\n", index, DBTypeLongName(index));
    for (index = 0; index < DBNumPlanes; index++)
        if (DBPlaneLongName(index))
            fprintf(OpenPLLSurfaceFile, "PLANE %d \"%s\"\n", index, DBPlaneLongName(index));
}

static void
OpenPLLTraceSurfaceRecord(char kind)
{
    OpenPLLSurfaceEvent++;
    if (OpenPLLSurfaceFile)
        fprintf(OpenPLLSurfaceFile, "SURFACE %lu %c %d %d %d %d %d %d\n",
            OpenPLLSurfaceEvent, kind,
            OpenPLLSurfaceContext[0], OpenPLLSurfaceContext[1], OpenPLLSurfaceContext[2],
            OpenPLLSurfaceContext[3], OpenPLLSurfaceContext[4], OpenPLLSurfaceContext[5]);
    OpenPLLTraceSurfaceContext(-1, -1, -1, -1, -1, -1);
}

static void
OpenPLLTraceSurfaceEnd(void)
{
    if (!OpenPLLSurfaceFile) return;
    fprintf(OpenPLLSurfaceFile, "END %lu\n", OpenPLLSurfaceEvent);
    if (fclose(OpenPLLSurfaceFile) != 0) { perror("OPENPLL surface close"); exit(2); }
    OpenPLLSurfaceFile = NULL;
}
'''


def main():
    base = ROOT/'build/timing400/release_001'
    source = ROOT/'build/timing400/magic_location_source_001'
    prior = base/'magic_R_binding_trace_patch_004/assessment.json'
    proof = verify(prior)
    for path, value in proof['diagnostic_source_files'].items():
        assert sha(path) == value
    basic = source/'extract/ExtBasic.c'
    text = basic.read_text()
    marker = 'FILE *OpenPLLTraceFile = NULL;'
    assert text.count(marker) == 1
    text = text.replace(marker, marker+'\n'+HELPER)
    marker = '        fprintf(OpenPLLTraceFile, " unlocated\\n");\n}'
    assert text.count(marker) == 2
    # Ground and pair are the only two primitive record writers.
    text = text.replace(marker, '        fprintf(OpenPLLTraceFile, " unlocated\\n");\n    OpenPLLTraceSurfaceRecord(\'G\');\n}', 1)
    text = text.replace(marker, '        fprintf(OpenPLLTraceFile, " unlocated\\n");\n    OpenPLLTraceSurfaceRecord(\'P\');\n}', 1)
    marker = 'OpenPLLTraceGroundTile(NodeRegion *node, CapValue delta, Tile *tile,\n        const char *reason)'
    assert text.count(marker) == 1
    text = text.replace(marker, 'OpenPLLTraceGroundTile(NodeRegion *node, CapValue delta, Tile *tile,\n        const char *reason, int plane, int raw_type, int residue)')
    marker = '    TITORECT(tile, &support);\n    OpenPLLTraceGround(node, delta, &support, reason);'
    assert text.count(marker) == 1
    text = text.replace(marker, '    TITORECT(tile, &support);\n    OpenPLLTraceSurfaceContext(plane, raw_type, residue, -1, -1, -1);\n    OpenPLLTraceGround(node, delta, &support, reason);')
    for reason, count in [('tile_area', 1), ('tile_perimeter', 5)]:
        marker = 'tile, "'+reason+'");'
        assert text.count(marker) == count
        text = text.replace(marker, 'tile, "'+reason+'", tilePlaneNum, type, residue);')
    marker = '    OpenPLLTraceEnabled = (getenv("OPENPLL_CAP_TRACE_SUPPORT") != NULL);'
    assert text.count(marker) == 1
    text = text.replace(marker, marker+r'''
    if (getenv("OPENPLL_CAP_SURFACE_FILE") && !OpenPLLTraceEnabled)
    { fprintf(stderr, "OPENPLL surface trace requires contribution tracing\n"); exit(2); }
''')
    marker = '        fprintf(OpenPLLTraceFile, "OPENPLL_BEGIN \\\"%s\\\" full_geometry\\n", def->cd_name);'
    assert text.count(marker) == 1
    text = text.replace(marker, marker+'\n        OpenPLLTraceSurfaceBegin(def->cd_name);')
    marker = '        fprintf(OpenPLLTraceFile, "OPENPLL_END\\n");'
    assert text.count(marker) == 1
    text = text.replace(marker, '        OpenPLLTraceSurfaceEnd();\n'+marker)
    # The one unlocated whole-node clamp retains an explicitly unknown surface.
    marker = 'OpenPLLTraceGround(reg, -reg->nreg_cap, (Rect *)NULL,\n                        "global_nonnegative_clamp");'
    if marker not in text:
        # Match the pinned code's existing indentation, without altering logic.
        import re
        match = re.search(r'OpenPLLTraceGround\(reg, -reg->nreg_cap, \(Rect \*\)NULL,\s*"([^"]+)"\);', text)
        assert match
        marker = match[0]
    text = text.replace(marker, 'do { OpenPLLTraceSurfaceContext(-1, -1, -1, -1, -1, -1); '+marker+' } while (0);')
    couple = source/'extract/ExtCouple.c'
    other = couple.read_text()
    marker = 'extern int OpenPLLTraceEnabled;'
    assert other.count(marker) == 1
    other = other.replace(marker, marker+'\nextern void OpenPLLTraceSurfaceContext(int, int, int, int, int, int);')
    changes = [
        ('OpenPLLTraceGround(rabove, rabove->nreg_cap - openpll_before, &ov.o_clip, "overlap_shield");',
         'ecpls->plane_of_tile, TiGetTypeExact(tabove), ta, -1, -1, -1', 1),
        ('OpenPLLTracePair(rabove, rbelow, extGetCapValue(he) - openpll_before, &ov.o_clip, &ov.o_clip, "parallel_overlap");',
         'ecpls->plane_of_tile, TiGetTypeExact(tabove), ta, ecpls->plane_checked, TiGetTypeExact(tbelow), tb', 1),
        ('OpenPLLTraceGround(rbp, rbp->nreg_cap - openpll_before, &bp->b_segment, "fringe_blocked_substrate");',
         'esws->plane_of_boundary, TiGetTypeExact(bp->b_inside), ta, -1, -1, -1', 1),
        ('OpenPLLTraceGround(rbp, rbp->nreg_cap - openpll_before, &bp->b_segment, "fringe_shield_with_roundoff");',
         'esws->plane_of_boundary, TiGetTypeExact(bp->b_inside), ta, -1, -1, -1', 2),
    ]
    for call, context, count in changes:
        marker = 'if (OpenPLLTraceEnabled) '+call
        assert other.count(marker) == count, call
        other = other.replace(marker, 'if (OpenPLLTraceEnabled) { OpenPLLTraceSurfaceContext('+context+'); '+call+' }')
    call = 'OpenPLLTracePair(rbp, rtp, extGetCapValue(he) - openpll_before, &bp->b_segment, &openpll_target, "edge_fringe");'
    assert other.count(call) == 2
    other = other.replace(call, 'OpenPLLTraceSurfaceContext(esws->plane_of_boundary, TiGetTypeExact(bp->b_inside), ta, esws->plane_checked, TiGetTypeExact(tp), tb); '+call)
    marker = 'overlap, sep, esws->extCoupleList, bp->b_inside);'
    assert other.count(marker) == 4
    other = other.replace(marker, 'overlap, sep, esws->extCoupleList, bp->b_inside, esws->plane_of_boundary);')
    marker = 'extCoupleList, openpll_origin)'
    assert other.count(marker) == 1
    other = other.replace(marker, 'extCoupleList, openpll_origin, openpll_plane)')
    marker = '    Tile *openpll_origin;'
    assert other.count(marker) == 1
    other = other.replace(marker, marker+'\n    int openpll_plane;')
    call = 'OpenPLLTracePair(rinside, rfar, extGetCapValue(he) - openpll_before, &openpll_a, &openpll_b, "sidewall");'
    marker = 'if (OpenPLLTraceEnabled) '+call
    assert other.count(marker) == 1
    other = other.replace(marker, '''if (OpenPLLTraceEnabled) {
        TileType openpll_inside, openpll_far;
        extGetBoundaryTypes2(bdir, openpll_origin, tpfar, &openpll_inside, &openpll_far);
        OpenPLLTraceSurfaceContext(openpll_plane, TiGetTypeExact(openpll_origin), openpll_inside,
            openpll_plane, TiGetTypeExact(tpfar), openpll_far);
        '''+call+'\n    }')
    out = base/'magic_C_surface_trace_patch_001'
    out.mkdir(exist_ok=False)
    # Validate every edit before touching the shared diagnostic worktree.
    basic.write_text(text)
    couple.write_text(other)
    files = [Path(p).relative_to(source) for p in proof['diagnostic_source_files']]
    patch = ''
    for name in files:
        native = subprocess.check_output(['git', '-C', str(source), 'show', '8.3.623:'+str(name)], text=True)
        changed = (source/name).read_text()
        (out/('patched_'+name.name)).write_text(changed)
        patch += ''.join(difflib.unified_diff(native.splitlines(True), changed.splitlines(True), fromfile='a/'+str(name), tofile='b/'+str(name)))
    (out/'change.patch').write_text(patch)
    save(out/'assessment.json', dict(input_sha256={str(p): sha(p) for p in [Path(__file__).resolve(), prior, source/'database/database.h']},
        artifacts={str(p): sha(p) for p in out.iterdir()},
        diagnostic_source_files={str(source/f): sha(source/f) for f in files},
        contribution_stream_format_unchanged=True, separate_ordered_surface_metadata=True,
        calculator_plane_tile_type_and_contact_residue_retained=True,
        native_C_R_arithmetic_and_native_output_statements_unchanged=True,
        native_equivalence_and_complete_surface_alignment_controls_required=True,
        release_qualified=False, adopted=False))
    print('Prepared per-contribution capacitor plane/material stream; native equivalence and complete alignment controls required.')


if __name__ == '__main__':
    main()
