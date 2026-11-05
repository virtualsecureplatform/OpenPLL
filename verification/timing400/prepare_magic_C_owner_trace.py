#!/usr/bin/env python3
"""Record ownership and otherwise skipped self-coupling without changing C.

An opt-in side stream identifies pair-kernel conductors/layers, including equal
ideal-conductor pairs. Self-sidewall calls record geometry/rules and return
before touching the native coupling hash. Installed tools remain untouched.
"""
import json
from pathlib import Path
import subprocess
import time

from compile_local_C_operators_v2 import digest, save


OWNER_IMPLEMENTATION = r'''
static FILE *OpenPLLKernelOwnerFile = NULL;
static unsigned long OpenPLLKernelOwnerCount = 0;
int OpenPLLKernelOwnersEnabled(void)
{
    return OpenPLLKernelOwnerFile != NULL;
}
void OpenPLLKernelOwner(unsigned long id, void *a, void *b,
    int pa, int ra, int ea, int pb, int rb, int eb)
{
    if (!id || !OpenPLLKernelOwnerFile) return;
    OpenPLLKernelOwnerCount++;
    fprintf(OpenPLLKernelOwnerFile, "OWNER %lu %p %p %d %d %d %d %d %d %d\n",
        id, a, b, pa, ra, ea, pb, rb, eb, a == b);
}
'''


def replace(text, old, new, count=1):
    assert text.count(old) == count, (old[:90], text.count(old), count)
    return text.replace(old, new)


def main():
    root = Path(__file__).resolve().parents[2]
    base = root/'build/timing400/release_001'
    owner = base/'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    prep_path = base/'magic_C_owner_source_preparation_001/assessment.json'
    prep = json.loads(prep_path.read_text())
    assert prep['isolated_C_kernel_source_reproduced']
    assert all(digest(Path(p)) == v for p, v in prep['reproduced_source_sha256'].items())
    source = root/'build/timing400/magic_C_owner_source_001'
    header = source/'extract/OpenPLLChargeTrace.h'
    text = header.read_text()
    text = replace(text, '#ifdef OPENPLL_CHARGE_TRACE_IMPLEMENTATION',
        'int OpenPLLKernelOwnersEnabled(void);\nvoid OpenPLLKernelOwner(unsigned long, void *, void *, int, int, int, int, int, int);\n#ifdef OPENPLL_CHARGE_TRACE_IMPLEMENTATION\n'+OWNER_IMPLEMENTATION)
    text = replace(text, '    const char *path = getenv("OPENPLL_CAP_KERNEL_FILE");',
        '    const char *path = getenv("OPENPLL_CAP_KERNEL_FILE");\n    const char *owners = getenv("OPENPLL_CAP_OWNER_FILE");\n    if (owners && !path) { fprintf(stderr, "owners require kernel stream\\n"); exit(2); }')
    text = replace(text, '    fprintf(OpenPLLKernelFile, "BEGIN \\"%s\\"\\n", cell);'.replace('\\\\', '\\'),
        '    fprintf(OpenPLLKernelFile, "BEGIN \\"%s\\"\\n", cell);'.replace('\\\\', '\\')+r'''
    if (owners) {
        OpenPLLKernelOwnerFile = fopen(owners, "wx");
        if (!OpenPLLKernelOwnerFile) { perror("OPENPLL_CAP_OWNER_FILE"); exit(2); }
        OpenPLLKernelOwnerCount = 0;
        fprintf(OpenPLLKernelOwnerFile, "BEGIN \"%s\"\n", cell);
    }
''')
    text = replace(text, '    OpenPLLKernelFile = NULL;', r'''    OpenPLLKernelFile = NULL;
    if (OpenPLLKernelOwnerFile) {
        fprintf(OpenPLLKernelOwnerFile, "END %lu %lu\n", OpenPLLKernelOwnerCount, OpenPLLKernelCount);
        if (fclose(OpenPLLKernelOwnerFile) != 0) { perror("owner stream close"); exit(2); }
        OpenPLLKernelOwnerFile = NULL;
    }''')
    header.write_text(text)
    couple = source/'extract/ExtCouple.c'
    text = couple.read_text()
    marker = '    ov.openpll_kernel = OpenPLLKernelBegin("OVERLAP", &ov.o_clip, &ov.o_clip, -1);'
    text = replace(text, marker, marker+'''
    OpenPLLKernelOwner(ov.openpll_kernel, (void *)rabove, (void *)rbelow,
        ecpls->plane_of_tile, TiGetTypeExact(tabove), ta,
        ecpls->plane_checked, TiGetTypeExact(tbelow), tb);''')
    marker = '    sov.openpll_kernel = OpenPLLKernelBegin("FRINGE_HALO", &bp->b_segment, &sov.so_clip, bp->b_direction);'
    text = replace(text, marker, marker+'''
    {
        TileType owner_a = ta, owner_b = tb;
        if (DBIsContact(owner_a)) owner_a = DBPlaneToResidue(owner_a, esws->plane_of_boundary);
        if (DBIsContact(owner_b)) owner_b = DBPlaneToResidue(owner_b, esws->plane_checked);
        OpenPLLKernelOwner(sov.openpll_kernel, (void *)rbp, (void *)rtp,
            esws->plane_of_boundary, TiGetTypeExact(bp->b_inside), owner_a,
            esws->plane_checked, TiGetTypeExact(tp), owner_b);
    }''')
    text = replace(text, 'rfar != (NodeRegion *) CLIENTDEFAULT && rfar != rinside',
        'rfar != (NodeRegion *) CLIENTDEFAULT && (rfar != rinside || OpenPLLKernelOwnersEnabled())', count=3)
    text = replace(text, 'rfar != (NodeRegion *)CLIENTDEFAULT && rfar != rinside',
        'rfar != (NodeRegion *)CLIENTDEFAULT && (rfar != rinside || OpenPLLKernelOwnersEnabled())')
    marker = '    extGetBoundaryTypes2(bdir, tpnear, tpfar, &near, &far);'
    text = replace(text, marker, marker+'''
    {
        TileType owner_a, owner_b;
        extGetBoundaryTypes2(bdir, openpll_origin, tpfar, &owner_a, &owner_b);
        OpenPLLKernelOwner(openpll_id, (void *)rinside, (void *)rfar,
            openpll_plane, TiGetTypeExact(openpll_origin), owner_a,
            openpll_plane, TiGetTypeExact(tpfar), owner_b);
    }
    if (rinside == rfar) {
        for (e = extCoupleList; e; e = e->ec_next)
            if (TTMaskHasType(&e->ec_near, near) && TTMaskHasType(&e->ec_far, far))
                OpenPLLKernelValues(openpll_id, "SIDEWALL_RULE", ++openpll_rule,
                    e->ec_cap, e->ec_offset, 0, 0, 0, 0, 0, 0);
        return;
    }''')
    couple.write_text(text)
    subprocess.run(['git', '-C', str(source), 'add', '-N', 'extract/OpenPLLChargeTrace.h'], check=True)
    names = subprocess.check_output(['git', '-C', str(source), 'diff', '--name-only'], text=True).splitlines()
    out = base/'magic_C_owner_trace_patch_001'
    out.mkdir(exist_ok=False)
    (out/'change.patch').write_bytes(subprocess.check_output(['git', '-C', str(source), 'diff', '--binary']))
    for p in [header, couple]:
        (out/('patched_'+p.name)).write_bytes(p.read_bytes())
    inputs = [Path(__file__).resolve(), owner, prep_path,
        base/'DCO_local_C_matrix_nom_checks_001/assessment.json',
        root/'build/timing400/magic_C_kernel_source_001/extract/OpenPLLChargeTrace.h',
        root/'build/timing400/magic_C_kernel_source_001/extract/ExtCouple.c']
    result = dict(pair_kernel_owner_and_skipped_self_sidewall_diagnostics_added=True,
        all_native_hash_and_ground_updates_preserved=True,
        self_sidewall_diagnostic_returns_before_native_hash=True,
        diagnostic_source_files={str(source/n): digest(source/n) for n in names},
        input_sha256={str(p): digest(p) for p in inputs},
        artifacts={str(p): digest(p) for p in out.iterdir()},
        native_equivalence_controls_required=True, installed_extractor_replaced=False,
        runtime_model_eligible=False, release_qualified=False, adopted=False, deadline_uptime=deadline)
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    save(out/'assessment.json', result)
    print('Isolated owner diagnostics patched; build and native equivalence controls are required.')


if __name__ == '__main__':
    main()
