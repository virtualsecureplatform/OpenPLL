#!/usr/bin/env python3
"""Trace device bindings, node lifetimes and one-breakpoint conductor tiles.

Preserve native arithmetic, names, file records and reduction controls. Private
event streams identify mesh vertices independently of aliased printed names.
SPICE device IDs receive geometry keys so original device parameters can be
associated with the physical binding without guessing instance order.
"""
import difflib
from pathlib import Path
import re
import subprocess
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT, sha, save


BIND_HELPER = r'''
static FILE *
OpenPLLRBindStream(void)
{
    const char *path = getenv("OPENPLL_R_BIND_TRACE_FILE");
    static FILE *stream = NULL;
    if (!path) return NULL;
    if (!stream)
    {
        stream = fopen(path, "wx");
        if (!stream) { perror("OPENPLL_R_BIND_TRACE_FILE"); exit(2); }
    }
    return stream;
}

void
OpenPLLRBindAlloc(resNode *node)
{
    FILE *stream = OpenPLLRBindStream();
    if (stream) fprintf(stream, "ALLOC %p\n", (void *)node);
}

void
OpenPLLRBindMerge(resNode *keep, resNode *remove)
{
    FILE *stream = OpenPLLRBindStream();
    if (stream) fprintf(stream, "MERGE %p %p\n", (void *)keep, (void *)remove);
}

void
OpenPLLRBindDevice(RDev *dev, int terminal, resNode *node)
{
    FILE *stream = OpenPLLRBindStream();
    if (stream) fprintf(stream, "BIND %p %d %d %u \"%s\" %d %p\n",
        (void *)dev, dev->location.p_x, dev->location.p_y,
        (unsigned)dev->rs_ttype, dev->rs_devptr->exts_deviceName,
        terminal, (void *)node);
}

void
OpenPLLRBindSingle(Tile *tile, resNode *node)
{
    FILE *stream = OpenPLLRBindStream();
    if (stream) fprintf(stream, "SINGLE %p %d %d %d %d %u %d\n",
        (void *)node, LEFT(tile), BOTTOM(tile), RIGHT(tile), TOP(tile),
        (unsigned)TiGetTypeExact(tile), IsSplit(tile) ? 1 : 0);
}

static void
OpenPLLRBindGroup(unsigned long group, const char *original)
{
    FILE *stream = OpenPLLRBindStream();
    if (!stream) return;
    fprintf(stream, "GROUP %lu \"%s\"\n", group, original);
    if (fflush(stream) != 0 || ferror(stream))
    { perror("OPENPLL_R_BIND_TRACE flush"); exit(2); }
}
'''


def main():
    base = ROOT/'build/timing400/release_001'
    source = ROOT/'build/timing400/magic_location_source_001'
    previous = base/'magic_retained_R_mesh_patch_001/assessment.json'
    for path, value in verify(previous)['diagnostic_source_files'].items():
        assert sha(path) == value
    pending = {}
    printer = source/'resis/ResPrint.c'
    text = printer.read_text()
    marker = 'static unsigned long\nOpenPLLRNodeBegin'
    assert text.count(marker) == 1
    text = text.replace(marker, BIND_HELPER+'\n'+marker)
    marker = '    OpenPLLRNodeGroup++;'
    assert text.count(marker) == 1
    text = text.replace(marker, '    OpenPLLRBindGroup(OpenPLLRNodeGroup + 1, original);\n'+marker)
    pending[printer] = text
    allocation_counts = {}
    for name in ['ResBasic.c', 'ResMakeRes.c', 'ResJunct.c', 'ResMerge.c']:
        path = source/'resis'/name
        text = path.read_text()
        marker = '#include "resis/resis.h"'
        assert text.count(marker) == 1
        declarations = '\nextern void OpenPLLRBindAlloc(resNode *);\n'
        if name == 'ResMakeRes.c':
            declarations += 'extern void OpenPLLRBindSingle(Tile *, resNode *);\n'
        if name == 'ResMerge.c':
            declarations += 'extern void OpenPLLRBindMerge(resNode *, resNode *);\n'
        text = text.replace(marker, marker+declarations)
        pattern = r'(\b(\w+)\s*=\s*\(resNode\s*\*\)\s*mallocMagic[^;]*;)'
        text, count = re.subn(pattern, lambda m: m[1]+'\n        OpenPLLRBindAlloc('+m[2]+');', text)
        assert count > 0, name
        allocation_counts[name] = count
        if name == 'ResMakeRes.c':
            pattern = r'(if\s*\(p1->br_next == NULL\)\n    \{)'
            text, count = re.subn(pattern, lambda m: m[1]+'\n        OpenPLLRBindSingle(tile, p1->br_this);', text)
            assert count == 2
        if name == 'ResMerge.c':
            marker = '    /* don\'t want to merge away start or end points */'
            assert text.count(marker) == 1
            text = text.replace(marker, '    OpenPLLRBindMerge(node1, node2);\n\n'+marker)
        pending[path] = text
    rex = source/'resis/ResRex.c'
    text = rex.read_text()
    native = subprocess.check_output(['git', '-C', str(source), 'show', '8.3.623:resis/ResRex.c'], text=True)
    assert text == native
    marker = '#include "resis/resis.h"'
    assert text.count(marker) == 1
    text = text.replace(marker, marker+'\nextern void OpenPLLRBindDevice(RDev *, int, resNode *);\n')
    start = text.index('void\nResFixDevName(')
    end = text.index('\n}\n', start)
    text = text[:end]+'\n    OpenPLLRBindDevice(device, type, layoutnode);'+text[end:]
    pending[rex] = text
    path = source/'ext2spice/ext2spice.c'
    text = path.read_text()
    original = subprocess.check_output(['git', '-C', str(source), 'show', '8.3.623:ext2spice/ext2spice.c'], text=True)
    assert text == original
    # The DCO exports modelled subcircuits with sequential X IDs, no gate attrs.
    # Trace inside that exact numbering branch, before its native increment.
    marker = '\t\tfprintf(esSpiceF, "%d", esSbckNum++);'
    assert text.count(marker) == 1
    helper = r'''
        {
            const char *trace_path = getenv("OPENPLL_SPICE_DEVICE_TRACE_FILE");
            static FILE *trace_stream = NULL;
            if (trace_path)
            {
                if (!trace_stream)
                {
                    trace_stream = fopen(trace_path, "wx");
                    if (!trace_stream) { perror("OPENPLL_SPICE_DEVICE_TRACE_FILE"); exit(2); }
                }
                fprintf(trace_stream, "DEVICE X%d \"%s\" %d %d %d %d %d %d\n",
                    esSbckNum, EFDevTypes[dev->dev_type], dev->dev_rect.r_xbot,
                    dev->dev_rect.r_ybot, dev->dev_rect.r_xtop, dev->dev_rect.r_ytop, l, w);
                if (fflush(trace_stream) != 0 || ferror(trace_stream))
                { perror("OPENPLL_SPICE_DEVICE_TRACE flush"); exit(2); }
            }
        }
'''
    text = text.replace(marker, helper+marker)
    pending[path] = text
    out = base/'magic_R_binding_trace_patch_002'
    out.mkdir(exist_ok=False)
    for path, contents in pending.items():
        path.write_text(contents)
    files = ['resis/ResPrint.c', 'resis/ResBasic.c', 'resis/ResMakeRes.c', 'resis/ResJunct.c',
             'resis/ResMerge.c', 'resis/ResRex.c', 'ext2spice/ext2spice.c',
             'extract/ExtBasic.c', 'extract/ExtCouple.c', 'extract/ExtCell.c']
    patch = ''
    for name in files:
        original = subprocess.check_output(['git', '-C', str(source), 'show', '8.3.623:'+name], text=True)
        changed = (source/name).read_text()
        (out/('patched_'+Path(name).name)).write_text(changed)
        patch += ''.join(difflib.unified_diff(original.splitlines(True), changed.splitlines(True), fromfile='a/'+name, tofile='b/'+name))
    (out/'change.patch').write_text(patch)
    save(out/'assessment.json', dict(input_sha256={str(p): sha(p) for p in [Path(__file__).resolve(), previous, source/'resis/resis.h', base/'DCO_R_export_alias_audit_002/assessment.json']},
        artifacts={str(p): sha(p) for p in out.iterdir()},
        diagnostic_source_files={str(source/f): sha(source/f) for f in files},
        allocation_logging_sites=allocation_counts,
        private_node_lifetime_device_binding_and_single_tile_stream=True,
        private_SPICE_device_geometry_ID_stream=True,
        extraction_and_output_arithmetic_unchanged=True, native_controls_required=True,
        release_qualified=False, adopted=False))
    print('Prepared private native node lifetime/device binding and SPICE geometry traces:', allocation_counts)


if __name__ == '__main__':
    main()
