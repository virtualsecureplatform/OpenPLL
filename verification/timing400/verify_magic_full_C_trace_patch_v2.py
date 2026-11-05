#!/usr/bin/env python3
"""Reconstruct and verify the exact second tracer source patch without mutation."""
from pathlib import Path
from run_dco_qualification import ROOT,sha,save
from check_compact_clock_tree import verify


def main():
    base=ROOT/'build/timing400/release_001'
    prior=base/'magic_full_C_trace_patch_001/assessment.json';current=base/'magic_full_C_trace_patch_002/assessment.json'
    verify(prior);verify(current)
    old='if (OpenPLLTraceEnabled) OpenPLLTracePair(rbp, rtp, extGetCapValue(he) - openpll_before, &bp->b_segment, &tpr, "edge_fringe");'
    new='if (OpenPLLTraceEnabled) { Rect openpll_target; TITORECT(tp, &openpll_target); OpenPLLTracePair(rbp, rtp, extGetCapValue(he) - openpll_before, &bp->b_segment, &openpll_target, "edge_fringe"); }'
    paths=[Path(__file__).resolve(),prior,current]
    for name in ['ExtBasic.c','ExtCouple.c']:
        before=prior.parent/('patched_'+name);after=current.parent/('patched_'+name)
        text=before.read_text()
        if name=='ExtCouple.c':assert text.count(old)==2;text=text.replace(old,new)
        assert text==after.read_text();paths.extend([before,after])
    out=base/'magic_full_C_trace_patch_derivation_002';out.mkdir(exist_ok=False)
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in paths},artifacts={},
        exact_second_source_patch_reconstructed=True,only_two_trace_support_expressions_changed=True,
        native_arithmetic_unchanged=True,release_qualified=False))
    print('Exact second tracer source patch independently reconstructed.')


if __name__=='__main__':main()
