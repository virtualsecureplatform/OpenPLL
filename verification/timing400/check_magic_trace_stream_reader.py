#!/usr/bin/env python3
"""Cross-check streaming accounting on12 completed native controls.

Add a synthetic terminal marker to retained old-format records for reader
comparison only. This is not new native private-file qualification. Reject
truncation, reversed support bounds and an omitted real contribution.
"""
from pathlib import Path
from decimal import Decimal
from stream_magic_full_C_trace import reconstruct_stream
from check_magic_full_C_trace_v3 import reconstruct,compare,native
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT,sha,save


def main():
    base=ROOT/'build/timing400/release_001';prior=base/'magic_full_C_trace_controls_003/assessment.json'
    assert verify(prior)['full_geometry_trace_accounting_controls_passed']
    out=base/'magic_full_C_trace_stream_reader_controls_001';out.mkdir(exist_ok=False)
    paths=[Path(__file__).resolve(),Path(__file__).with_name('stream_magic_full_C_trace.py'),
        Path(__file__).with_name('check_magic_full_C_trace_v3.py'),prior];results=[]
    for folder in sorted(prior.parent.glob('*_*')):
        if not folder.is_dir():continue
        source=folder/'trace.log';text=source.read_text();target=out/(folder.name+'.derived.log')
        target.write_text(''.join(l+'\n' for l in text.splitlines() if l.startswith('OPENPLL_'))+'OPENPLL_END\n')
        a,abs_a,events,counts,ids=reconstruct(text)
        b,abs_b,count,count_b,ids_b,stats=reconstruct_stream(target)
        assert (a,abs_a,len(events),counts,ids)==(b,abs_b,count,count_b,ids_b)
        expected,rounding,nodes=native(next(folder.glob('*.ext')))
        differences,worst=compare(expected,b,rounding,abs_b,count);assert not differences
        damaged=dict(b);k=tuple(stats['largest_nonself_event_nodes']);damaged[k]-=Decimal(stats['largest_nonself_event_delta_ff'])
        assert compare(expected,damaged,rounding,abs_b,count)[0]
        results.append(dict(case=folder.name,events=count,stream_and_original_reader_exactly_equal=True,
            native_matrix_reconstructed=True,missing_real_contribution_rejected=True));paths.append(source)
    assert len(results)==12
    sample=next(out.glob('*.derived.log')).read_text()
    for name,text in [('truncated',sample.replace('OPENPLL_END\n','')),('reversed_box',sample.replace(' box ',' box 1 1 -1 -1 # ',1))]:
        fault=out/(name+'.fault.log');fault.write_text(text)
        try:reconstruct_stream(fault)
        except (AssertionError,ValueError):pass
        else:raise AssertionError(name+' accepted')
    save(out/'comparison.json',results)
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in paths},
        artifacts={str(p):sha(p) for p in out.iterdir()},stream_reader_controls_passed=True,
        compared_native_control_logs=12,synthetic_end_marker_only_for_parser_comparison=True,
        truncation_bad_bounds_and_missing_real_contribution_rejected=True,
        native_CAD_runs_added=0,native_private_trace_file_qualified=False,release_qualified=False))
    print('Streaming reader agrees exactly on12 native logs; malformed/truncated/missing-contribution controls rejected.')


if __name__=='__main__':main()
