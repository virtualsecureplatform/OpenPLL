#!/usr/bin/env python3
"""Instrument original full-geometry C updates; never use rejected clipping.

Log actual accumulator deltas, node identities, conservative tile/boundary
supports, and final negative-ground clamp corrections. Keep native arithmetic
statements unchanged. Original source and complete patch are retained. The
trace must reproduce native output before spatial/timing/model use.
"""
import difflib
from pathlib import Path
import re
import subprocess
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT,sha,save

HELPERS=r'''
/* OpenPLL opt-in full-geometry diagnostics. No clipping or formula changes. */
int OpenPLLTraceEnabled = 0;

void
OpenPLLTraceGround(NodeRegion *node, CapValue delta, const Rect *support,
        const char *reason)
{
    if (!OpenPLLTraceEnabled || delta == 0.0) return;
    fprintf(stderr, "OPENPLL_G %p %.17g %s", (void *)node,
            (double)(delta / ExtCurStyle->exts_capScale), reason);
    if (support != NULL)
        fprintf(stderr, " box %d %d %d %d\n", support->r_xbot,
                support->r_ybot, support->r_xtop, support->r_ytop);
    else
        fprintf(stderr, " unlocated\n");
}

void
OpenPLLTraceGroundTile(NodeRegion *node, CapValue delta, Tile *tile,
        const char *reason)
{
    Rect support;
    if (!OpenPLLTraceEnabled || delta == 0.0) return;
    TITORECT(tile, &support);
    OpenPLLTraceGround(node, delta, &support, reason);
}

void
OpenPLLTracePair(NodeRegion *a, NodeRegion *b, CapValue delta,
        const Rect *support_a, const Rect *support_b, const char *reason)
{
    if (!OpenPLLTraceEnabled || delta == 0.0) return;
    fprintf(stderr, "OPENPLL_P %p %p %.17g %s", (void *)a, (void *)b,
            (double)(delta / ExtCurStyle->exts_capScale), reason);
    if (support_a != NULL && support_b != NULL)
        fprintf(stderr, " boxes %d %d %d %d %d %d %d %d\n",
                support_a->r_xbot, support_a->r_ybot,
                support_a->r_xtop, support_a->r_ytop,
                support_b->r_xbot, support_b->r_ybot,
                support_b->r_xtop, support_b->r_ytop);
    else
        fprintf(stderr, " unlocated\n");
}
'''

EXTERNS=r'''
extern int OpenPLLTraceEnabled;
extern void OpenPLLTraceGround(NodeRegion *, CapValue, const Rect *, const char *);
extern void OpenPLLTracePair(NodeRegion *, NodeRegion *, CapValue,
        const Rect *, const Rect *, const char *);
'''


def wrap_ground(statement,node,support,reason,tile=False):
    call='OpenPLLTraceGroundTile' if tile else 'OpenPLLTraceGround'
    return ('do {\n    CapValue openpll_before = '+node+'->nreg_cap;\n    '+statement+
        '\n    if (OpenPLLTraceEnabled) '+call+'('+node+', '+node+'->nreg_cap - openpll_before, '+support+', "'+reason+'");\n} while (0);')


def wrap_pair(statement,a,b,sa,sb,reason,extra=''):
    return ('{\n    CapValue openpll_before = extGetCapValue(he);\n'+extra+'\n    '+statement+
        '\n    if (OpenPLLTraceEnabled) OpenPLLTracePair('+a+', '+b+', extGetCapValue(he) - openpll_before, '+sa+', '+sb+', "'+reason+'");\n}')


def main():
    base=ROOT/'build/timing400/release_001';source=ROOT/'build/timing400/magic_location_source_001'
    baseline=base/'isolated_magic_stock_controls_003/assessment.json';assert verify(baseline)['installed_and_isolated_C_devices_feedback_equal']
    prior_path=base/'magic_cap_clip_source_patch_002/assessment.json';prior=verify(prior_path)
    failed=base/'magic_cap_clip_window_controls_001/assessment.json';assert not verify(failed)['initial_C_window_accounting_controls_passed']
    for p,d in prior['diagnostic_source_files'].items():assert sha(p)==d,p
    originals={name:(base/'magic_cap_clip_source_patch_002'/('original_'+name)).read_text() for name in ['ExtBasic.c','ExtCouple.c']}
    for name,text in originals.items():
        assert text==subprocess.check_output(['git','-C',str(source),'show','8.3.623:extract/'+name],text=True)
    basic=originals['ExtBasic.c'];couple=originals['ExtCouple.c']
    marker='/* --------------------- Data local to this file ---------------------- */'
    # Insert before extBasic, after native type definitions are available.
    where=basic.index('\nNodeRegion *\nextBasic(')
    basic=basic[:where]+'\n'+HELPERS+'\n'+basic[where:]
    marker='    bool isabstract = FALSE;\n\n    glob_subsnode = (NodeRegion *)NULL;'
    assert basic.count(marker)==1
    basic=basic.replace(marker,'''    bool isabstract = FALSE;

    OpenPLLTraceEnabled = (getenv("OPENPLL_CAP_TRACE_SUPPORT") != NULL);
    if (OpenPLLTraceEnabled)
    {
        if (!(ExtOptions & EXT_DOCAPACITANCE) || !(ExtOptions & EXT_DOCOUPLING))
        {
            fprintf(stderr, "OPENPLL_TRACE requires capacitance and coupling\\n");
            exit(2);
        }
        fprintf(stderr, "OPENPLL_BEGIN \\\"%s\\\" full_geometry\\n", def->cd_name);
    }
    glob_subsnode = (NodeRegion *)NULL;''')
    marker='    propptr = DBPropGetString(def, "device", &propfound);'
    assert basic.count(marker)==2
    basic=basic.replace(marker,marker+'''\n    if (OpenPLLTraceEnabled && propfound)
    {
        fprintf(stderr, "OPENPLL_TRACE: device-property parasitic removal unsupported\\n");
        exit(2);
    }''',1)
    marker='\ttext = extNodeName((LabRegion *) reg);'
    assert basic.count(marker)==1
    basic=basic.replace(marker,marker+'''\n        if (OpenPLLTraceEnabled)
            fprintf(stderr, "OPENPLL_ID %p \\\"%s\\\" %d\\n", (void *)reg,
                    text, reg == glob_subsnode);''')
    marker='\t    if (finC < 0.0) finC = 0.0;'
    assert basic.count(marker)==1
    basic=basic.replace(marker,'''            if (OpenPLLTraceEnabled && finC < 0.0)
                OpenPLLTraceGround(reg, -reg->nreg_cap, (Rect *)NULL,
                        "output_zero_clamp");
'''+marker)
    statement='reg->nreg_cap += area * ExtCurStyle->exts_areaCap[residue];'
    assert basic.count(statement)==1
    basic=basic.replace(statement,wrap_ground(statement,'reg','tile','tile_area',True))
    statement='reg->nreg_cap += capval * len;';assert basic.count(statement)==5
    basic=basic.replace(statement,wrap_ground(statement,'reg','tile','tile_perimeter',True))
    # The original full extraction calls remain NULL: no clipping is introduced.
    assert 'extFindNodes(def, (Rect *) NULL, FALSE);' in basic
    assert 'extFindCoupling(def, &extCoupleHash, (Rect *) NULL);' in basic
    couple=couple.replace('#include <stdio.h>','#include <stdio.h>\n#include <stdlib.h>')
    where=couple.index('/* --------------------- Data local to this file ---------------------- */')
    couple=couple[:where]+EXTERNS+'\n'+couple[where:]
    statement='rabove->nreg_cap -= ExtCurStyle->exts_areaCap[ta] * ov.o_area;';assert couple.count(statement)==1
    couple=couple.replace(statement,wrap_ground(statement,'rabove','&ov.o_clip','overlap_shield'))
    # Preserve each original near-zero adjustment inside the same delta capture.
    pattern=r'rbp->nreg_cap -= subcap;\n(?P<comment>\s*/\* Ignore residual error[\s\S]*?\*/\n)\s*if \(\(rbp->nreg_cap > -0\.001\) && \(rbp->nreg_cap < 0\.001\)\)\n\s*rbp->nreg_cap = 0;'
    matches=list(re.finditer(pattern,couple));assert len(matches)==2
    for match in reversed(matches):
        original=match[0]
        couple=couple[:match.start()]+wrap_ground(original,'rbp','&bp->b_segment','fringe_shield_with_roundoff')+couple[match.end():]
    statement='rbp->nreg_cap -= subcap;'
    # The two wrapped statements plus one remaining unwrapped removal.
    index=couple.index(statement)
    couple=couple[:index]+wrap_ground(statement,'rbp','&bp->b_segment','fringe_blocked_substrate')+couple[index+len(statement):]
    statement='extSetCapValue(he, c);';assert couple.count(statement)==1
    couple=couple.replace(statement,wrap_pair(statement,'rabove','rbelow','&ov.o_clip','&ov.o_clip','parallel_overlap'))
    statement='extSetCapValue(he, cap + extGetCapValue(he));';assert couple.count(statement)==2
    couple=couple.replace(statement,wrap_pair(statement,'rbp','rtp','&bp->b_segment','&tpr','edge_fringe'))
    # Pass the actual origin tile to sidewall support logging; formulas are intact.
    assert couple.count('overlap, sep, esws->extCoupleList);')==4
    couple=couple.replace('overlap, sep, esws->extCoupleList);','overlap, sep, esws->extCoupleList, bp->b_inside);')
    old='extSideCommon(rinside, rfar, tpnear, tpfar, bdir, overlap, sep, extCoupleList)';assert couple.count(old)==1
    couple=couple.replace(old,old[:-1]+', openpll_origin)')
    marker='    EdgeCap  *extCoupleList;\t/* List of sidewall capacitance rules */\n{'
    assert couple.count(marker)==1
    couple=couple.replace(marker,marker[:-1]+'    Tile *openpll_origin;\n{')
    statement='extSetCapValue(he, cap);';assert couple.count(statement)==1
    couple=couple.replace(statement,wrap_pair(statement,'rinside','rfar','&openpll_a','&openpll_b','sidewall',
        '    Rect openpll_a, openpll_b;\n    TITORECT(openpll_origin, &openpll_a);\n    TITORECT(tpfar, &openpll_b);'))
    out=base/'magic_full_C_trace_patch_001';out.mkdir(exist_ok=False)
    patched={'ExtBasic.c':basic,'ExtCouple.c':couple};patch=''
    for name,text in patched.items():
        (out/('original_'+name)).write_text(originals[name]);(out/('patched_'+name)).write_text(text)
        patch+=''.join(difflib.unified_diff(originals[name].splitlines(True),text.splitlines(True),fromfile='a/extract/'+name,tofile='b/extract/'+name))
        (source/'extract'/name).write_text(text)
    (out/'change.patch').write_text(patch)
    assert set(subprocess.check_output(['git','-C',str(source),'diff','--name-only'],text=True).splitlines())=={'extract/ExtBasic.c','extract/ExtCouple.c'}
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in [Path(__file__).resolve(),baseline,prior_path,failed]},
        artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()},
        diagnostic_source_files={str(source/'extract'/name):sha(source/'extract'/name) for name in patched},
        upstream_base_commit='fd12c39c37f26a0fe6e04698b1011e31b8bd3229',full_geometry_used=True,
        native_capacitance_arithmetic_statements_retained=True,existing_clipping_not_used=True,
        conservative_supports_logged=True,unlocated_output_clamp_adjustments_explicit=True,
        trace_reconstruction_and_support_validation_passed=False,
        installed_tools_replaced=False,physical_timing_qualified=False,release_qualified=False,adopted=False,scope=__doc__))
    print('Prepared full-geometry C accumulator trace; baseline, reconstruction and spatial support validation remain required.')


if __name__=='__main__':main()
