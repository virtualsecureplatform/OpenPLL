#!/usr/bin/env python3
"""Trace every R tile's breakpoint domain in a fresh isolated source tree."""
from pathlib import Path
import subprocess
import time
import json
from run_dco_qualification import ROOT, sha, save


HELPER = r'''
/* Optional complete tile-domain diagnostics, including zero-R collapsed tiles. */
static int
OpenPLLWorkingPlane(Tile *tile)
{
    int plane;
    Point p;
    p.p_x = LEFT(tile);
    p.p_y = BOTTOM(tile);
    for (plane = 0; plane < DBNumPlanes; plane++)
        if (ResUse && ResUse->cu_def->cd_planes[plane] &&
            TiSrPoint((Tile *)NULL, ResUse->cu_def->cd_planes[plane], &p) == tile)
            return plane;
    return -1;
}

void
OpenPLLRBindTileDomain(Tile *tile, resInfo *info)
{
    FILE *stream;
    Breakpoint *bp;
    static unsigned long serial = 0;
    int count = 0;
    if (!getenv("OPENPLL_R_TILE_DOMAIN_TRACE")) return;
    stream = OpenPLLRBindStream();
    if (!stream) return;
    serial++;
    for (bp = info->breakList; bp; bp = bp->br_next) count++;
    fprintf(stream, "TILE %lu %p %d %u %d %d %d %d %d %d\n", serial, (void *)tile,
        OpenPLLWorkingPlane(tile), (unsigned)TiGetTypeExact(tile), IsSplit(tile) ? 1 : 0,
        LEFT(tile), BOTTOM(tile), RIGHT(tile), TOP(tile), count);
    for (bp = info->breakList; bp; bp = bp->br_next)
        fprintf(stream, "TBP %lu %p %d %d\n", serial, (void *)bp->br_this, bp->br_loc.p_x, bp->br_loc.p_y);
}

void
OpenPLLRBindContactDomain(ResContactPoint *contact, int index, resNode *node)
{
    FILE *stream;
    Tile *tile;
    if (!getenv("OPENPLL_R_TILE_DOMAIN_TRACE")) return;
    stream = OpenPLLRBindStream();
    if (!stream) return;
    tile = contact->cp_tile[index];
    fprintf(stream, "CONTACT %p %p %d %d %u %d %p %u %d %d %d %d %d %d\n",
        (void *)contact, (void *)node, index, contact->cp_currentcontact, (unsigned)contact->cp_type,
        OpenPLLWorkingPlane(tile), (void *)tile, (unsigned)TiGetTypeExact(tile),
        contact->cp_center.p_x, contact->cp_center.p_y,
        contact->cp_rect.r_xbot, contact->cp_rect.r_ybot, contact->cp_rect.r_xtop, contact->cp_rect.r_ytop);
}
'''


def main():
    base = ROOT/'build/timing400/release_001'
    owner = base/'distributed_RC_model_qualification_001/owner.json'
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < json.loads(owner.read_text())['deadline_uptime']
    old = ROOT/'build/timing400/magic_location_source_001'
    source = ROOT/'build/timing400/magic_R_tile_domain_source_001'
    out = base/'magic_R_tile_domain_trace_patch_001'
    assert not source.exists()
    out.mkdir(exist_ok=False)
    commit = subprocess.check_output(['git', '-C', str(old), 'rev-parse', 'HEAD'], text=True).strip()
    assert commit == 'fd12c39c37f26a0fe6e04698b1011e31b8bd3229'
    baseline = subprocess.check_output(['git', '-C', str(old), 'diff', '--binary'])
    (out/'baseline.patch').write_bytes(baseline)
    subprocess.run(['git', '-C', str(old), 'worktree', 'add', '--quiet', '--detach', str(source), commit], check=True)
    subprocess.run(['git', '-C', str(source), 'apply', '--whitespace=nowarn', str(out/'baseline.patch')], check=True)
    original_files = subprocess.check_output(['git', '-C', str(old), 'diff', '--name-only'], text=True).splitlines()
    for name in original_files:
        assert sha(old/name) == sha(source/name)
    path = source/'resis/ResPrint.c'
    text = path.read_text()
    marker = 'void\nOpenPLLRBindAlloc(resNode *node)'
    assert text.count(marker) == 1
    text = text.replace(marker, HELPER+'\n'+marker)
    path.write_text(text)
    path = source/'resis/ResMakeRes.c'
    text = path.read_text()
    marker = 'extern void OpenPLLRBindAlloc(resNode *);'
    assert text.count(marker) == 1
    text = text.replace(marker, marker+'\nextern void OpenPLLRBindTileDomain(Tile *, resInfo *);\nextern void OpenPLLRBindContactDomain(ResContactPoint *, int, resNode *);')
    marker = '    if ((p1 = info->breakList) == NULL) return FALSE;'
    assert text.count(marker) == 1
    text = text.replace(marker, '    OpenPLLRBindTileDomain(tile, info);\n'+marker)
    marker = '    contact->cp_cnode[tilenum] = resptr;'
    assert text.count(marker) == 2
    text = text.replace(marker, marker+'\n        OpenPLLRBindContactDomain(contact, tilenum, resptr);')
    path.write_text(text)
    files = subprocess.check_output(['git', '-C', str(source), 'diff', '--name-only'], text=True).splitlines()
    (out/'change.patch').write_bytes(subprocess.check_output(['git', '-C', str(source), 'diff', '--binary']))
    for name in files:
        (out/('patched_'+Path(name).name)).write_bytes((source/name).read_bytes())
    save(out/'assessment.json', dict(input_sha256={str(p): sha(p) for p in [Path(__file__).resolve(), owner, *[old/n for n in original_files]]},
        artifacts={str(p): sha(p) for p in out.iterdir()},
        diagnostic_source_files={str(source/n): sha(source/n) for n in files},
        isolated_source=str(source), upstream_commit=commit,
        complete_pre_merge_tile_breakpoint_and_contact_working_plane_trace_prepared=True,
        previous_sources_modified=False, native_numerical_equivalence_controls_passed=False,
        physical_voltage_domain_coverage_qualified=False, release_qualified=False, adopted=False))
    print('Prepared isolated all-tile/contact-domain trace; no R arithmetic or geometry edits; compile/native controls required.')


if __name__ == '__main__':
    main()
