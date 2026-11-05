#!/usr/bin/env python3
"""Retain native resistor creation geometry without changing extraction maths.

Node coordinates can be representatives of a much larger equipotential region.
Record the actual tile and breakpoint coordinates at branch creation, and the
branch pointer at final export. Pointer reuse is resolved in stream order.
The isolated diagnostic must pass native network equivalence before use.
"""
import difflib
from pathlib import Path
import subprocess
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT, sha, save


def main():
    base = ROOT/'build/timing400/release_001'
    source = ROOT/'build/timing400/magic_location_source_001'
    prior = base/'magic_R_node_trace_patch_001/assessment.json'
    proof = verify(prior)
    for p, digest in proof['diagnostic_source_files'].items():
        assert sha(p) == digest, p
    path = source/'resis/ResMakeRes.c'
    original = subprocess.check_output(['git', '-C', str(source), 'show', '8.3.623:resis/ResMakeRes.c'], text=True)
    assert path.read_text() == original
    text = original.replace('/* Forward declarations */',
        'extern void OpenPLLRSegmentRecord(resResistor *, Tile *, Point *, Point *);\n\n/* Forward declarations */', 1)
    marker = '    rArea = ((p2->br_loc.p_x - p1->br_loc.p_x) * height) / 2;'
    assert text.count(marker) == 1
    text = text.replace(marker, '    OpenPLLRSegmentRecord(resistor, tile, &p1->br_loc, &p2->br_loc);\n'+marker)
    marker = '    rArea = ((p2->br_loc.p_y - p1->br_loc.p_y) * width) / 2;'
    assert text.count(marker) == 1
    text = text.replace(marker, '    OpenPLLRSegmentRecord(resistor, tile, &p1->br_loc, &p2->br_loc);\n'+marker)
    # Contacts use a different rr_cl/rr_width meaning; leave them as contacts.
    # Their endpoints/locations already appear in the node provenance stream.
    path.write_text(text)
    printer = source/'resis/ResPrint.c'
    old_printer = printer.read_text()
    marker = 'static void\nOpenPLLRNodeRecord(unsigned long group, resNode *node)'
    helper = r'''
void
OpenPLLRSegmentRecord(resResistor *res, Tile *tile, Point *a, Point *b)
{
    FILE *stream = OpenPLLRSegmentStream();
    if (!stream) return;
    fprintf(stream, "SEG %p %p %p %d %d %d %d %d %d %d %d %.17g %u %d %d %d\n",
        (void *)res, (void *)res->rr_node[0], (void *)res->rr_node[1],
        a->p_x, a->p_y, b->p_x, b->p_y,
        LEFT(tile), BOTTOM(tile), RIGHT(tile), TOP(tile),
        (double)res->rr_value, (unsigned)res->rr_tt, res->rr_status,
        res->rr_cl, res->rr_width);
    if (fflush(stream) != 0 || ferror(stream))
    { perror("OPENPLL_R_SEGMENT_TRACE flush"); exit(2); }
}

'''
    assert old_printer.count(marker) == 1
    stream_helper = r'''
+static FILE *
+OpenPLLRSegmentStream(void)
+{
+    const char *path = getenv("OPENPLL_R_SEGMENT_TRACE_FILE");
+    static FILE *stream = NULL;
+    if (!path) return NULL;
+    if (!stream)
+    {
+        stream = fopen(path, "wx");
+        if (!stream) { perror("OPENPLL_R_SEGMENT_TRACE_FILE"); exit(2); }
+    }
+    return stream;
+}
+'''.replace('\n+', '\n')
    new_printer = old_printer.replace('static unsigned long\nOpenPLLRNodeBegin', stream_helper+'\nstatic unsigned long\nOpenPLLRNodeBegin', 1)
    new_printer = new_printer.replace(marker, helper+marker)
    marker = '    OpenPLLRNodeGroup++;'
    # Order the separate creation stream at every exported group boundary.
    replacement = r'''    {
        FILE *stream = OpenPLLRSegmentStream();
        if (stream)
        {
            fprintf(stream, "GROUP %lu \"%s\"\n", OpenPLLRNodeGroup + 1, original);
            if (fflush(stream) != 0 || ferror(stream))
            { perror("OPENPLL_R_SEGMENT_TRACE flush"); exit(2); }
        }
    }
'''+marker
    assert new_printer.count(marker) == 1
    new_printer = new_printer.replace(marker, replacement)
    # Separate identity record preserves the established EDGE record schema.
    marker = '        resResistor *res = incident->re_thisEl;'
    assert new_printer.count(marker) == 1
    new_printer = new_printer.replace(marker, marker+r'''
        if (getenv("OPENPLL_R_SEGMENT_TRACE_FILE"))
            fprintf(OpenPLLRNodeFile, "BRANCH %lu %p %p\n", group, (void *)node, (void *)res);
''')
    printer.write_text(new_printer)
    out = base/'magic_R_segment_trace_patch_001'
    out.mkdir(exist_ok=False)
    files = ['resis/ResMakeRes.c', 'resis/ResPrint.c', 'extract/ExtBasic.c', 'extract/ExtCouple.c', 'extract/ExtCell.c']
    patch = ''
    for name in files:
        upstream = subprocess.check_output(['git', '-C', str(source), 'show', '8.3.623:'+name], text=True)
        changed = (source/name).read_text()
        (out/('patched_'+Path(name).name)).write_text(changed)
        patch += ''.join(difflib.unified_diff(upstream.splitlines(True), changed.splitlines(True), fromfile='a/'+name, tofile='b/'+name))
    (out/'change.patch').write_text(patch)
    save(out/'assessment.json', dict(input_sha256={str(p): sha(p) for p in [Path(__file__).resolve(), prior, source/'resis/resis.h']},
        artifacts={str(p): sha(p) for p in out.iterdir()},
        diagnostic_source_files={str(source/f): sha(source/f) for f in files},
        native_R_C_arithmetic_and_native_output_statements_unchanged=True,
        creation_geometry_and_exported_branch_identity_logged=True,
        native_controls_required=True, release_qualified=False, adopted=False))
    print('Prepared isolated native resistor segment geometry tracer.')


if __name__ == '__main__':
    main()
