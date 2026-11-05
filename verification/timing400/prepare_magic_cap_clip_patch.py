#!/usr/bin/env python3
"""Expose existing native capacitance clipping in an isolated diagnostic build.

Keep capacitance arithmetic unchanged. An explicit environment rectangle in
Magic internal coordinates is passed to existing node/coupling clipping APIs.
Unsetting it retains NULL arguments. Flat layouts and additivity controls are
required; no physical model is qualified by preparing this patch.
"""
import difflib
import json
from pathlib import Path
import subprocess
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT,sha,save


def main():
    base=ROOT/'build/timing400/release_001'
    baseline=base/'isolated_magic_stock_controls_003/assessment.json'
    b=verify(baseline);assert b['installed_and_isolated_C_devices_feedback_equal'] and b['native_CAD_runs']==24
    source=ROOT/'build/timing400/magic_location_source_001'
    assert subprocess.check_output(['git','-C',str(source),'diff','--name-only'],text=True)==''
    path=source/'extract/ExtBasic.c';original=path.read_text()
    assert original==subprocess.check_output(['git','-C',str(source),'show','8.3.623:extract/ExtBasic.c'],text=True)
    marker='''    bool isabstract = FALSE;

    glob_subsnode = (NodeRegion *)NULL;'''
    assert original.count(marker)==1
    replacement='''    bool isabstract = FALSE;

    /* OpenPLL diagnostic: retain full connectivity, clip C accounting only.
     * Input is in Magic internal coordinates, and supported only on flat cells.
     * With no environment value, both existing clipping APIs receive NULL.
     */
    Rect openpllClipArea;
    Rect *openpllClip = (Rect *)NULL;
    const char *openpllClipText = getenv("OPENPLL_CAP_CLIP_INTERNAL");
    if (openpllClipText != NULL)
    {
        char extra;
        if (sscanf(openpllClipText, "%d %d %d %d %c",
                &openpllClipArea.r_xbot, &openpllClipArea.r_ybot,
                &openpllClipArea.r_xtop, &openpllClipArea.r_ytop, &extra) != 4
                || openpllClipArea.r_xbot >= openpllClipArea.r_xtop
                || openpllClipArea.r_ybot >= openpllClipArea.r_ytop)
        {
            fprintf(stderr, "OPENPLL_CAP_CLIP_INTERNAL: invalid rectangle\\n");
            exit(2);
        }
        openpllClip = &openpllClipArea;
        fprintf(stderr, "OPENPLL_CAP_CLIP_INTERNAL active: %d %d %d %d\\n",
                openpllClipArea.r_xbot, openpllClipArea.r_ybot,
                openpllClipArea.r_xtop, openpllClipArea.r_ytop);
    }

    glob_subsnode = (NodeRegion *)NULL;'''
    patched=original.replace(marker,replacement)
    for before,after in [
        ('nodeList = extFindNodes(def, (Rect *) NULL, FALSE);','nodeList = extFindNodes(def, openpllClip, FALSE);'),
        ('extFindCoupling(def, &extCoupleHash, (Rect *) NULL);','extFindCoupling(def, &extCoupleHash, openpllClip);')]:
        assert patched.count(before)==1;patched=patched.replace(before,after)
    node_marker='    finC = reg->nreg_cap/ExtCurStyle->exts_capScale;'
    # The file uses a tab at this point; match the expression exactly.
    node_marker='\t    finC = reg->nreg_cap/ExtCurStyle->exts_capScale;'
    assert patched.count(node_marker)==1
    node_trace='\n            if (getenv("OPENPLL_CAP_CLIP_INTERNAL") != NULL)\n                fprintf(stderr, "OPENPLL_CAP_NODE \\"%s\\" %.17g\\n",\n                        text, (double)finC);\n'
    patched=patched.replace(node_marker,node_marker+node_trace)
    couple_path=source/'extract/ExtCouple.c';original_couple=couple_path.read_text()
    assert original_couple==subprocess.check_output(['git','-C',str(source),'show','8.3.623:extract/ExtCouple.c'],text=True)
    couple_marker='\tck = (CoupleKey *) he->h_key.h_words;\n\ttext = extNodeName((LabRegion *) ck->ck_1);'
    assert original_couple.count(couple_marker)==1
    couple_trace='\n        if (getenv("OPENPLL_CAP_CLIP_INTERNAL") != NULL)\n        {\n            text = extNodeName((LabRegion *) ck->ck_1);\n            fprintf(stderr, "OPENPLL_CAP_COUPLE \\"%s\\" ", text);\n            text = extNodeName((LabRegion *) ck->ck_2);\n            fprintf(stderr, "\\"%s\\" %.17g\\n", text, (double)cap);\n        }\n'
    patched_couple=original_couple.replace(couple_marker,'\tck = (CoupleKey *) he->h_key.h_words;\n'+couple_trace+'\ttext = extNodeName((LabRegion *) ck->ck_1);')
    out=base/'magic_cap_clip_source_patch_001';out.mkdir(exist_ok=False)
    (out/'original_ExtBasic.c').write_text(original);(out/'patched_ExtBasic.c').write_text(patched)
    (out/'original_ExtCouple.c').write_text(original_couple);(out/'patched_ExtCouple.c').write_text(patched_couple)
    patch=''.join(difflib.unified_diff(original.splitlines(True),patched.splitlines(True),
        fromfile='a/extract/ExtBasic.c',tofile='b/extract/ExtBasic.c'))
    patch+=''.join(difflib.unified_diff(original_couple.splitlines(True),patched_couple.splitlines(True),
        fromfile='a/extract/ExtCouple.c',tofile='b/extract/ExtCouple.c'))
    (out/'change.patch').write_text(patch)
    path.write_text(patched);couple_path.write_text(patched_couple)
    assert set(subprocess.check_output(['git','-C',str(source),'diff','--name-only'],text=True).splitlines())=={'extract/ExtBasic.c','extract/ExtCouple.c'}
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in [Path(__file__).resolve(),baseline]},
        artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()},
        upstream_commit='fd12c39c37f26a0fe6e04698b1011e31b8bd3229',
        diagnostic_source_files={str(path):sha(path),str(couple_path):sha(couple_path)},
        signed_ground_and_coupling_values_traced_at17_significant_digits=True,
        negative_ground_before_existing_output_clamp_exposed=True,
        preexisting_capacitance_clipping_APIs_exposed=True,capacitance_arithmetic_modified=False,
        default_NULL_arguments_preserved_without_environment=True,
        flat_cells_only=True,clip_grid_additivity_proven=False,
        installed_extractor_replaced=False,physical_timing_qualified=False,
        release_qualified=False,adopted=False,scope=__doc__))
    print('Prepared isolated opt-in native C clipping patch; additivity and spatial/timing qualification remain unproven.')


if __name__=='__main__':main()
