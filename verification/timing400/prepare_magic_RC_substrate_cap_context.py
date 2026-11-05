#!/usr/bin/env python3
"""Opt into native RC substrate preparation without running full wire extraction.

Change only the two substrate-context conditions identified in upstream623.
Keep all C formulas and the existing contribution tracer. Opt-in default off;
flat-layout native controls must compare against installed resistance-enabled
extraction before applying this mode to any broad layout.
"""
from pathlib import Path
import difflib,subprocess
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT,sha,save


def main():
    base=ROOT/'build/timing400/release_001';source=ROOT/'build/timing400/magic_location_source_001'
    prior=base/'magic_full_C_trace_patch_003/assessment.json';v=verify(prior)
    semantics=base/'magic_resistance_substrate_semantics_001/assessment.json'
    assert verify(semantics)['nominal_R_context_exactly_recovers_retained_pre_RC_C']
    for p,d in v['diagnostic_source_files'].items():assert sha(p)==d,p
    original_cell=subprocess.check_output(['git','-C',str(source),'show','8.3.623:extract/ExtCell.c'],text=True)
    assert (source/'extract/ExtCell.c').read_text()==original_cell
    out=base/'magic_RC_substrate_C_patch_001';out.mkdir(exist_ok=False)
    diagnostic={};patch=''
    for name in ['ExtBasic.c','ExtCouple.c','ExtCell.c']:
        p=source/'extract'/name;text=p.read_text()
        original=original_cell if name=='ExtCell.c' else (base/'magic_full_C_trace_patch_001'/('original_'+name)).read_text()
        if name=='ExtCell.c':
            assert text.count('#include <stdio.h>')==1;text=text.replace('#include <stdio.h>','#include <stdio.h>\n#include <stdlib.h>')
            old='if (ExtOptions & EXT_DOEXTRESIST)\n\tsaveSub = extResPrepSubstrate(def);';assert text.count(old)==1
            text=text.replace(old,'if ((ExtOptions & EXT_DOEXTRESIST) || getenv("OPENPLL_CAP_RC_SUBSTRATE") != NULL)\n\tsaveSub = extResPrepSubstrate(def);')
        elif name=='ExtBasic.c':
            old='if (!(ExtOptions & EXT_DOEXTRESIST))\n\t    if (ExtCurStyle->exts_globSubstrateDefaultType != -1)';assert text.count(old)==1
            text=text.replace(old,'if (!(ExtOptions & EXT_DOEXTRESIST) && getenv("OPENPLL_CAP_RC_SUBSTRATE") == NULL)\n\t    if (ExtCurStyle->exts_globSubstrateDefaultType != -1)')
        (out/('original_'+name)).write_text(original);(out/('patched_'+name)).write_text(text)
        patch+=''.join(difflib.unified_diff(original.splitlines(True),text.splitlines(True),fromfile='a/extract/'+name,tofile='b/extract/'+name))
        p.write_text(text);diagnostic[str(p)]=sha(p)
    (out/'change.patch').write_text(patch)
    paths=[Path(__file__).resolve(),prior,semantics]
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in paths},artifacts={str(p):sha(p) for p in out.iterdir()},
        diagnostic_source_files=diagnostic,opt_in_environment='OPENPLL_CAP_RC_SUBSTRATE',
        only_two_substrate_conditions_changed_relative_to_tracer=True,all_native_C_arithmetic_preserved=True,
        full_geometry_used=True,automatic_full_wire_R_extraction_not_enabled_by_new_flag=True,
        flat_layout_controls_required=True,physical_timing_qualified=False,release_qualified=False,adopted=False))
    print('Prepared opt-in native RC substrate context for C-only extraction; native equivalence controls required.')


if __name__=='__main__':main()
