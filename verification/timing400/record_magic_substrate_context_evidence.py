#!/usr/bin/env python3
"""Pin upstream code explaining different native RC and C-only substrate contexts."""
from pathlib import Path
import subprocess
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT,sha,save


def main():
    base=ROOT/'build/timing400/release_001';source=ROOT/'build/timing400/magic_location_source_001'
    receipt=base/'DCO_resistance_enabled_C_context_001/assessment.json'
    r=verify(receipt);assert r['full_DCO_trace_accounting_passed']
    assert r['results'][0]['retained_pre_RC_exact_positive_C_matrix_equal']
    out=base/'magic_resistance_substrate_semantics_001';out.mkdir(exist_ok=False)
    commit='fd12c39c37f26a0fe6e04698b1011e31b8bd3229'
    text={}
    for name in ['extract/ExtCell.c','extract/ExtBasic.c','extract/ExtMain.c','resis/ResRex.c']:
        code=subprocess.check_output(['git','-C',str(source),'show',commit+':'+name],text=True)
        p=out/Path(name).name;p.write_text(code);text[name]=code
    assert '''if (ExtOptions & EXT_DOEXTRESIST)
\tsaveSub = extResPrepSubstrate(def);
    else
\tsaveSub = extPrepSubstrate(def);''' in text['extract/ExtCell.c']
    assert '''if (!(ExtOptions & EXT_DOEXTRESIST))
\t    if (ExtCurStyle->exts_globSubstrateDefaultType != -1)''' in text['extract/ExtBasic.c']
    assert 'Now that all cells have been processed, run full R-C extraction' in text['extract/ExtMain.c']
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in [Path(__file__).resolve(),receipt,
        base/'fresh_DCO_nominal_source_difference_001/assessment.json']},
        artifacts={str(p):sha(p) for p in out.iterdir()},upstream_commit=commit,
        RC_enabled_changes_substrate_preparation=True,RC_enabled_changes_default_substrate_type_membership=True,
        RC_enabled_extract_all_also_runs_native_resistance_extraction=True,
        nominal_R_context_exactly_recovers_retained_pre_RC_C=True,
        C_only_and_RC_contexts_not_interchangeable_without_proof=True,
        physical_bulk_resistance_or_junction_distribution_qualified=False,release_qualified=False,adopted=False))
    print('Upstream substrate-context semantics pinned; nominal RC-enabled extraction exactly recovers retained pre-RC C.')


if __name__=='__main__':main()
